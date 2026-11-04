"""AoE IV local match inspection panel and transparent name overlay."""
import csv,json,logging,math,os,statistics,sys,threading,time
from collections import Counter,deque
from dataclasses import asdict
from pathlib import Path
from logging.handlers import RotatingFileHandler
import tkinter as tk
from tkinter import ttk,filedialog,messagebox
from tkinter import font as tkfont
from reader import Reader,project,BUILD_SHA256
from reader_12260 import Reader as Reader12260, BUILD_SHA256 as BUILD_SHA256_12260
from memory import Process,game_pids
import hashlib
from windowing import U,dpi_aware,game_window,client_rect,clickthrough,place
from layout import arrange
from unit_names import NameStore,default_name
from name_editor import NameEditor
from assistance import IdleReminder,exclude_local
from live_assistance import snapshot as assistance_snapshot
from live_12260 import snapshot as assistance_snapshot_12260
from telemetry import PlayerTelemetry,PopulationWarning,MilitaryWarning,panels,number

HOME=Path(sys.executable).parent if getattr(sys,'frozen',False) else Path(__file__).resolve().parent
DATA=HOME/'config'
DATA.mkdir(parents=True,exist_ok=True)
log=logging.getLogger('lab');log.setLevel(logging.INFO)
handler=RotatingFileHandler(DATA/'lab.log',maxBytes=1_000_000,backupCount=2,encoding='utf-8')
handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'));log.addHandler(handler)

def short_name(blueprint):
    return default_name(blueprint)

def open_reader():
    ids=game_pids()
    if len(ids)!=1:raise RuntimeError(f'需要唯一游戏进程，当前检测到 {len(ids)} 个')
    p=Process(ids[0])
    try:
        module=next(m for m in p.modules() if m['name'].lower()=='reliccardinal.exe')
        with open(module['path'],'rb') as f:actual=hashlib.file_digest(f,'sha256').hexdigest()
    finally:p.close()
    if actual==BUILD_SHA256:
        reader=Reader(ids[0]);reader.version='17.0.12182.0';reader.verified=True
    else:
        reader=Reader12260(ids[0],expected_hash=actual)
        reader.verified=actual==BUILD_SHA256_12260
        reader.version='17.0.12260.0' if reader.verified else '未知版本（尝试 17.0.12260.0 配置，数据未经验证）'
    reader.build_sha256=actual
    return reader

class Sampler:
    def __init__(self):
        self.stop_event=threading.Event();self.lock=threading.Lock();self.thread=None
        self.config={'interval':100,'neutral':False};self.latest=None;self.status='尚未连接';self.times=deque(maxlen=120)
    def configure(self,**values):
        with self.lock:self.config.update(values)
    def start(self):
        if self.thread and self.thread.is_alive():
            if not self.stop_event.is_set():return
            self.thread.join(timeout=.5)
            if self.thread.is_alive():return
        self.stop_event.clear();self.times.clear()
        self.thread=threading.Thread(target=self.run,daemon=True,name='read-only-sampler');self.thread.start()
    def stop(self):
        self.stop_event.set()
        with self.lock:self.latest=None;self.status='已停止'
    def snapshot(self):
        with self.lock:return self.latest,self.status
    def run(self):
        reader=None;last_sample=0;last_camera=0;cam=None;entities=[];entity_stamp=0;last_neutral=None;errors=0;failures=0;next_attach=0;last_error='';last_error_log=0;aux={}
        try:
            while not self.stop_event.is_set():
                tick=time.perf_counter()
                with self.lock:cfg=dict(self.config)
                try:
                    if reader is None:
                        if tick<next_attach:
                            self.stop_event.wait(.1);continue
                        with self.lock:self.status='正在校验游戏版本并连接…'
                        reader=open_reader();last_sample=0;last_camera=0;cam=None;last_neutral=None
                        log.info('Attached pid=%s module_base=%#x',reader.p.pid,reader.base)
                    if tick-last_sample>=cfg['interval']/1000 or cfg['neutral']!=last_neutral:
                        start=time.perf_counter();entities,errors=reader.entities(cfg['neutral'])
                        aux=(assistance_snapshot_12260 if isinstance(reader,Reader12260) else assistance_snapshot)(reader,entities)
                        cost=(time.perf_counter()-start)*1000;self.times.append(cost)
                        last_sample=tick;entity_stamp=time.perf_counter();last_neutral=cfg['neutral']
                    if cam is None or tick-last_camera>=1/30:
                        cam=reader.camera();last_camera=tick
                    failures=0
                    packet={'pid':reader.p.pid,'entities':entities,'camera':cam,'time':time.perf_counter(),
                        'entity_time':entity_stamp,'count':reader.raw_count,'errors':errors+reader.errors,
                        'ms':self.times[-1] if self.times else 0,'median':statistics.median(self.times) if self.times else 0,
                        'interval':cfg['interval'],'read_calls':reader.p.read_calls,'version':reader.version,'build_sha256':reader.build_sha256,'verified':reader.verified,
                        **aux,
                        'match_key':(reader.p.pid,reader.arena,reader.world)}
                    if self.stop_event.is_set():break
                    with self.lock:self.latest=packet;self.status='已连接 · 真实内存数据' if reader.verified else '未知版本 · 使用旧配置尝试读取 · 数据未经验证'
                except Exception as e:
                    failures+=1;msg=f'{type(e).__name__}: {e}'
                    if reader and not reader.verified:msg='未知版本尝试读取失败（数据未经验证）：'+msg
                    if msg!=last_error or tick-last_error_log>5:log.warning(msg);last_error=msg;last_error_log=tick
                    with self.lock:self.latest=None;self.status=msg
                    if reader and failures>=3:reader.close();reader=None;next_attach=tick+2
                    if reader is None:next_attach=tick+2
                    self.stop_event.wait(.25)
                now=time.perf_counter()
                # Python 3.11+ uses a high-resolution waitable timer for sleep on
                # Windows. Event.wait can round a 20 ms deadline up to ~32 ms.
                # This sleep is bounded by the camera period (33 ms), including
                # when Stop is clicked; no process-wide timer setting is changed.
                time.sleep(max(.001,min(last_sample+cfg['interval']/1000-now,last_camera+1/30-now)))
        finally:
            if reader:reader.close()
            with self.lock:self.latest=None

class Overlay:
    def __init__(self,root):
        self.win=tk.Toplevel(root);self.win.withdraw();self.win.title('AoE IV Lab · Labels')
        self.win.overrideredirect(True);self.win.configure(bg='#010203')
        self.win.attributes('-topmost',True);self.win.attributes('-transparentcolor','#010203')
        self.canvas=tk.Canvas(self.win,bg='#010203',highlightthickness=0,bd=0);self.canvas.pack(fill='both',expand=True)
        self.hwnd=clickthrough(self.win);self.shown=False;self.items={};self.rect=None;self.last_font=None
    def hide(self):
        if self.shown:self.win.withdraw();self.shown=False
    def draw(self,rect,labels,font_size,tip='',side_panels=(),score_font=11,military_font=11):
        self.canvas.delete('assist_tip')
        if not self.shown:
            self.win.geometry(f'{rect[2]}x{rect[3]}+0+0');self.win.deiconify();self.hwnd=clickthrough(self.win);self.shown=True
            place(self.hwnd,rect);self.rect=rect
        elif self.rect!=rect:place(self.hwnd,rect);self.rect=rect
        live=set();font=('Microsoft YaHei UI',-font_size,'bold')
        for uid,x,y,tx,ty,text,color in arrange(labels,font_size,rect[2],rect[3]):
            live.add(uid)
            if uid not in self.items:
                line=self.canvas.create_line(x,y,tx,ty+3,fill=color,width=1)
                dot=self.canvas.create_oval(x-2,y-2,x+2,y+2,fill=color,outline='#10151e')
                shadow=self.canvas.create_text(tx+1,ty+1,text=text,fill='#060b12',font=font,anchor='s')
                main=self.canvas.create_text(tx,ty,text=text,fill=color,font=font,anchor='s')
                self.items[uid]=(line,dot,shadow,main,text,color)
            else:
                line,dot,shadow,main,oldtext,oldcolor=self.items[uid]
                self.canvas.coords(line,x,y,tx,ty+3);self.canvas.coords(dot,x-2,y-2,x+2,y+2)
                self.canvas.coords(shadow,tx+1,ty+1);self.canvas.coords(main,tx,ty)
                if text!=oldtext:self.canvas.itemconfigure(shadow,text=text);self.canvas.itemconfigure(main,text=text)
                if color!=oldcolor:
                    self.canvas.itemconfigure(line,fill=color);self.canvas.itemconfigure(dot,fill=color);self.canvas.itemconfigure(main,fill=color)
                if self.last_font!=font_size:
                    self.canvas.itemconfigure(shadow,font=font);self.canvas.itemconfigure(main,font=font)
                self.items[uid]=(line,dot,shadow,main,text,color)
        for uid in self.items.keys()-live:
            for item in self.items.pop(uid)[:4]:self.canvas.delete(item)
        self.draw_panels(rect,side_panels,score_font,military_font)
        if tip:
            w=rect[2];self.canvas.create_rectangle(w/2-310,26,w/2+310,96,fill='#352a17',outline='#eab85d',tags='assist_tip')
            self.canvas.create_text(w/2,61,text=tip,fill='#fff1cb',font=('Microsoft YaHei UI',14,'bold'),width=590,tags='assist_tip')
        self.last_font=font_size

    def draw_panels(self,rect,groups,score_font=11,military_font=11):
        signature=(rect[2],rect[3],groups,score_font,military_font)
        if signature==getattr(self,'panel_signature',None):
            self.canvas.tag_raise('telemetry');return
        self.panel_signature=signature;self.canvas.delete('telemetry')
        if not groups:return
        for title,rows in groups:
            right=title=='军事数据'
            x=rect[2]-12 if right else 12
            # Leave the top corners to the game HUD and chat.
            y=min(max(100,int(rect[3]*(.24 if right else .20))),max(0,rect[3]-100))
            font=('Microsoft YaHei UI',-(military_font if right else score_font))
            row_height=tkfont.Font(root=self.win,font=font).metrics('linespace')+2
            anchor='ne' if right else 'nw'
            def text_item(text,color,yy):
                self.canvas.create_text(x+1,yy+1,text=text,fill='#060b12',anchor=anchor,justify='right' if right else 'left',font=font,tags='telemetry')
                self.canvas.create_text(x,yy,text=text,fill=color,anchor=anchor,justify='right' if right else 'left',font=font,tags='telemetry')
            text_item(title,'#eef5ff',y)
            yy=y+row_height
            for text,color in rows:
                text_item(text,color,yy)
                yy+=(text.count('\n')+1)*row_height

class App:
    def __init__(self):
        dpi_aware();self.root=tk.Tk();self.root.title('AoE IV · 本机对局分析');self.root.geometry('1100x900')
        self.root.minsize(950,800);self.root.configure(bg='#101722');self.root.protocol('WM_DELETE_WINDOW',self.close)
        self.sampler=Sampler();self.overlay=Overlay(self.root);self.target=None;self.target_pid=None
        self.names=NameStore(DATA/'unit_names.json');self.name_editor=None;self.last_name_save=0
        self.last_table=0;self.last_window=0;self.packet=None;self.closing=False;self.visible=0
        self.interval=tk.StringVar(value='100');self.font_size=tk.StringVar(value='14');self.neutral=tk.BooleanVar(value=False)
        self.score_font=tk.StringVar(value='11');self.military_font=tk.StringVar(value='11')
        self.enabled=tk.BooleanVar(value=True);self.buildings=tk.BooleanVar(value=True);self.labelstyle=tk.StringVar(value='自定义 / 默认名称')
        self.player=tk.StringVar(value='全部玩家');self.status=tk.StringVar(value='尚未连接');self.note=tk.StringVar(value='')
        self.hide_self=tk.BooleanVar(value=False);self.idle_alert=tk.BooleanVar(value=False)
        self.auto_villager=tk.BooleanVar(value=False);self.assist_player=tk.StringVar(value='本机玩家')
        self.local_status=tk.StringVar(value='本机玩家：待识别');self.assist_status=tk.StringVar(value='等待对局数据；生产队列适配尚未验证')
        self.reminder=IdleReminder();self.tip='';self.tip_until=0;self.assist_context=None
        self.extra_flags={k:tk.BooleanVar(value=False) for k in ('evacuate','population','scores','military','intelligence')}
        self.extra_status=tk.StringVar(value='新增辅助等待数据适配；撤离不会发送指令')
        self.population_warning=PopulationWarning();self.military_warning=MilitaryWarning()
        self.extra_tip='';self.extra_tip_until=0;self.extra_messages=deque(maxlen=16);self.extra_context=None
        self.side_panels=[];self.last_telemetry=0
        self.stats={k:tk.StringVar(value='—') for k in ['units','raw','read','visible']}
        self.load_settings();self.make_ui();self.root.after(30,self.tick)
        self.root.after(250,self.start)
    def load_settings(self):
        try:
            d=json.loads((DATA/'settings.json').read_text(encoding='utf-8'))
            self.interval.set(str(max(20,min(2000,int(d.get('interval',100))))));self.font_size.set(str(max(10,min(28,int(d.get('font',14))))))
            self.score_font.set(str(max(8,min(28,int(d.get('score_font',11))))));self.military_font.set(str(max(8,min(28,int(d.get('military_font',11))))))
            self.neutral.set(bool(d.get('neutral',False)));self.buildings.set(bool(d.get('buildings',True)))
            self.hide_self.set(d.get('hide_self') is True);self.idle_alert.set(d.get('idle_alert') is True)
            for key,var in self.extra_flags.items():
                if key!='evacuate':var.set(d.get('assist_'+key) is True)
        except (OSError,ValueError,TypeError):pass
    def make_ui(self):
        style=ttk.Style();style.theme_use('clam')
        style.configure('.',font=('Microsoft YaHei UI',10),background='#101722',foreground='#dbe5f4')
        style.configure('TFrame',background='#101722');style.configure('Card.TFrame',background='#192432')
        style.configure('TLabel',background='#101722',foreground='#dbe5f4')
        style.configure('Muted.TLabel',foreground='#8b9caf');style.configure('Title.TLabel',font=('Microsoft YaHei UI',23,'bold'))
        style.configure('TButton',padding=(13,8),background='#25374d',foreground='#eaf1ff',borderwidth=0)
        style.map('TButton',background=[('active','#35526f')])
        style.configure('TCheckbutton',background='#101722',foreground='#dbe5f4')
        style.map('TCheckbutton',background=[('active','#101722')])
        style.configure('TCombobox',fieldbackground='#202e40',background='#25374d',foreground='#eaf1ff',arrowcolor='#dbe5f4')
        style.map('TCombobox',fieldbackground=[('readonly','#202e40')],foreground=[('readonly','#eaf1ff')])
        style.configure('TSpinbox',fieldbackground='#202e40',foreground='#eaf1ff',arrowcolor='#dbe5f4')
        style.configure('TEntry',fieldbackground='#202e40',foreground='#eaf1ff',insertcolor='#eaf1ff')
        style.configure('Treeview',background='#131e2b',fieldbackground='#131e2b',foreground='#dbe5f4',rowheight=29,borderwidth=0)
        style.configure('Treeview.Heading',background='#243246',foreground='#aebed2',padding=(7,8),borderwidth=0)
        style.map('Treeview',background=[('selected','#25476b')],foreground=[('selected','#ffffff')])
        outer=ttk.Frame(self.root,padding=24);outer.pack(fill='both',expand=True)
        top=ttk.Frame(outer);top.pack(fill='x')
        ttk.Label(top,text='对局观察台',style='Title.TLabel').pack(side='left')
        ttk.Label(top,text='AOE IV  /  LOCAL MATCH LAB',style='Muted.TLabel').pack(side='right',pady=10)
        ttk.Label(outer,text='单位名称、阵营颜色与实时位置',style='Muted.TLabel').pack(anchor='w',pady=(4,18))
        bar=ttk.Frame(outer);bar.pack(fill='x')
        self.start_button=ttk.Button(bar,text='连接 / 重试',command=self.start);self.start_button.pack(side='left')
        ttk.Button(bar,text='停止读取',command=self.stop).pack(side='left',padx=8)
        ttk.Button(bar,text='单位名称配置',command=self.edit_names).pack(side='left')
        ttk.Button(bar,text='导出当前快照',command=self.export).pack(side='right')
        opts=ttk.Frame(outer);opts.pack(fill='x',pady=(16,8))
        ttk.Label(opts,text='采样间隔').pack(side='left')
        ttk.Spinbox(opts,from_=20,to=2000,increment=10,width=6,textvariable=self.interval).pack(side='left',padx=(8,4))
        ttk.Label(opts,text='ms',style='Muted.TLabel').pack(side='left',padx=(0,16))
        ttk.Label(opts,text='标签字号').pack(side='left')
        ttk.Spinbox(opts,from_=10,to=28,width=4,textvariable=self.font_size).pack(side='left',padx=8)
        ttk.Label(opts,text='分数字号').pack(side='left',padx=(6,0))
        ttk.Spinbox(opts,from_=8,to=28,width=3,textvariable=self.score_font).pack(side='left',padx=6)
        ttk.Label(opts,text='军事字号').pack(side='left',padx=(6,0))
        ttk.Spinbox(opts,from_=8,to=28,width=3,textvariable=self.military_font).pack(side='left',padx=6)
        ttk.Button(opts,text='应用',command=self.apply).pack(side='left',padx=4)
        ttk.Checkbutton(opts,text='画面标签',variable=self.enabled).pack(side='left',padx=(16,0))
        opts2=ttk.Frame(outer);opts2.pack(fill='x',pady=(0,16))
        ttk.Checkbutton(opts2,text='包括建筑',variable=self.buildings).pack(side='left')
        ttk.Checkbutton(opts2,text='包括中立实体',variable=self.neutral,command=self.apply).pack(side='left',padx=16)
        ttk.Combobox(opts2,textvariable=self.labelstyle,values=['自定义 / 默认名称','完整蓝图名称'],state='readonly',width=17).pack(side='left',padx=(0,12))
        self.player_combo=ttk.Combobox(opts2,textvariable=self.player,values=['全部玩家'],state='readonly',width=12);self.player_combo.pack(side='left')
        ttk.Checkbutton(opts2,text='屏蔽自己',variable=self.hide_self,command=self.apply).pack(side='left',padx=12)
        ttk.Label(outer,textvariable=self.local_status,style='Muted.TLabel').pack(anchor='w',pady=(0,8))
        assist=ttk.Frame(outer,padding=10);assist.pack(fill='x',pady=(0,12))
        ttk.Label(assist,text='游玩辅助',font=('Microsoft YaHei UI',13,'bold')).pack(anchor='w')
        assist_row=ttk.Frame(assist);assist_row.pack(fill='x',pady=8)
        ttk.Checkbutton(assist_row,text='断农提醒',variable=self.idle_alert,command=self.apply).pack(side='left')
        ttk.Label(assist_row,text='提醒视角').pack(side='left',padx=(16,8))
        self.assist_combo=ttk.Combobox(assist_row,textvariable=self.assist_player,values=['本机玩家'],state='readonly',width=14);self.assist_combo.pack(side='left')
        self.auto_button=ttk.Checkbutton(assist_row,text='自动造农（执行器待适配）',variable=self.auto_villager,state='disabled');self.auto_button.pack(side='left',padx=20)
        ttk.Label(assist,textvariable=self.assist_status,style='Muted.TLabel',wraplength=980).pack(anchor='w')
        extra=ttk.Frame(assist);extra.pack(fill='x',pady=(8,4))
        for index,(key,label) in enumerate([('evacuate','受袭撤离助手'),('population','爆人口提醒'),('scores','实时分数显示'),('military','军事数据间谍'),('intelligence','军情六处警示助手')]):
            ttk.Checkbutton(extra,text=label+('（待适配）' if key=='evacuate' else ''),variable=self.extra_flags[key],command=self.extra_changed,state='disabled' if key=='evacuate' else 'normal').grid(row=index//3,column=index%3,sticky='w',padx=(0,20),pady=3)
        ttk.Label(assist,textvariable=self.extra_status,style='Muted.TLabel',wraplength=980).pack(anchor='w')
        cards=ttk.Frame(outer);cards.pack(fill='x',pady=(0,18))
        for i,(key,label) in enumerate([('units','筛选后的实体'),('raw','世界实体总数'),('read','采样耗时 / 中位数'),('visible','当前视野内标签')]):
            box=ttk.Frame(cards,style='Card.TFrame',padding=(16,12));box.grid(row=0,column=i,sticky='nsew',padx=(0,10 if i<3 else 0));cards.columnconfigure(i,weight=1)
            tk.Label(box,text=label,bg='#192432',fg='#8fa3ba',font=('Microsoft YaHei UI',10)).pack(anchor='w')
            tk.Label(box,textvariable=self.stats[key],bg='#192432',fg='#e2edf9',font=('Segoe UI',19,'bold')).pack(anchor='w',pady=(4,0))
        frame=ttk.Frame(outer);frame.pack(fill='both',expand=True)
        columns=('player','name','blueprint','position','id')
        self.table=ttk.Treeview(frame,columns=columns,show='headings',selectmode='browse',height=5)
        for key,title,width in [('player','玩家',65),('name','名称',120),('blueprint','真实蓝图名称',355),('position','世界坐标 X / Y / Z',210),('id','实体 ID',115)]:
            self.table.heading(key,text=title);self.table.column(key,width=width,minwidth=50,stretch=key in ('blueprint','position'))
        scroll=ttk.Scrollbar(frame,orient='vertical',command=self.table.yview);self.table.configure(yscrollcommand=scroll.set)
        self.table.pack(side='left',fill='both',expand=True);scroll.pack(side='right',fill='y')
        self.table.bind('<Double-1>',self.edit_selected_name)
        ttk.Label(outer,textvariable=self.status,wraplength=1000).pack(anchor='w',pady=(14,4))
        ttk.Label(outer,textvariable=self.note,style='Muted.TLabel',wraplength=1000).pack(anchor='w')
        self.note.set('标签只在游戏处于前台时显示；切回此窗口可调整参数。名称可切换为真实蓝图名称。')
    def apply(self):
        try:
            interval=int(self.interval.get());font=int(self.font_size.get());score_font=int(self.score_font.get());military_font=int(self.military_font.get())
            if not 20<=interval<=2000 or not 10<=font<=28 or not 8<=score_font<=28 or not 8<=military_font<=28:raise ValueError()
        except ValueError:
            self.note.set('请输入 20–2000 ms 的采样间隔、10–28 的标签字号和 8–28 的面板字号。');return False
        self.sampler.configure(interval=interval,neutral=self.neutral.get());self.render_font=font
        self.render_score_font=score_font;self.render_military_font=military_font
        d={'interval':interval,'font':font,'neutral':self.neutral.get(),'buildings':self.buildings.get()}
        d.update(score_font=score_font,military_font=military_font)
        d.update(hide_self=self.hide_self.get(),idle_alert=self.idle_alert.get())
        d.update({'assist_'+k:v.get() for k,v in self.extra_flags.items() if k!='evacuate'})
        try:
            tmp=DATA/'settings.tmp';tmp.write_text(json.dumps(d),encoding='utf-8');tmp.replace(DATA/'settings.json')
        except OSError as e:log.warning('Settings: %s',e)
        self.note.set(f'采样间隔 {interval} ms · 相机刷新 30 Hz · 标签仅在游戏前台显示')
        return True
    def start(self):
        if self.apply():self.sampler.start()
    def stop(self):
        self.sampler.stop();self.overlay.hide();self.packet=None
    def edit_names(self,selected=None):
        if self.packet:self.names.observe(e.blueprint for e in self.packet['entities'])
        if self.name_editor and not self.name_editor.closed:
            self.name_editor.win.lift()
            if selected:self.name_editor.query.set(selected)
            return
        self.name_editor=NameEditor(self,selected)
    def edit_selected_name(self,event):
        iid=self.table.identify_row(event.y)
        if iid:
            values=self.table.item(iid,'values')
            if values:self.edit_names(values[2])
    def filtered(self,entities):
        result=[];wanted=self.player.get()
        for e in exclude_local(entities,self.hide_self.get(),(self.packet or {}).get('local_player')):
            if not self.buildings.get() and e.blueprint.startswith('building_'):continue
            if wanted!='全部玩家' and wanted!=('中立' if e.player==0 else f'玩家 {e.player}'):continue
            result.append(e)
        return result
    def refresh_table(self,entities):
        ids=set();selected=self.table.selection();selection=selected[0] if selected else None
        for e in entities:
            iid=str(e.id);ids.add(iid);tag=f'p{e.player}';self.table.tag_configure(tag,foreground=e.color)
            values=('中立' if not e.player else f'P{e.player}',self.names.display(e.blueprint),e.blueprint,' / '.join(f'{v:.2f}' for v in e.position),e.id)
            if self.table.exists(iid):self.table.item(iid,values=values,tags=(tag,))
            else:self.table.insert('', 'end',iid=iid,values=values,tags=(tag,))
        for iid in set(self.table.get_children())-ids:self.table.delete(iid)
        if selection and self.table.exists(selection):self.table.selection_set(selection)
    def update_assistance(self,packet,valid,now):
        if not valid:
            self.reminder.reset();self.tip='';self.assist_context=None;self.auto_villager.set(False)
            self.local_status.set('本机玩家：待识别');self.assist_status.set('等待有效对局数据；生产队列适配尚未验证')
            return
        local=packet.get('local_player');match=packet.get('match_key');context=(match,self.assist_player.get(),self.idle_alert.get())
        if context!=self.assist_context:self.tip='';self.assist_context=context
        self.local_status.set(f'本机玩家：玩家 {local}' if local else '本机玩家：未识别；屏蔽自己暂不生效')
        players=sorted({e.player for e in packet['entities'] if e.player})
        options=['本机玩家']+[f'玩家 {n}' for n in players];self.assist_combo.configure(values=options)
        if self.assist_player.get() not in options:self.assist_player.set('本机玩家')
        selected=self.assist_player.get();player=local if selected=='本机玩家' else int(selected.split()[-1])
        verified=packet.get('queue_verified',False)
        alerts=self.reminder.update(match,player,packet.get('queues',[]),now,self.idle_alert.get() and verified)
        if alerts:
            self.tip=f'断农提醒 · 玩家 {player}\n{len(alerts)} 座城镇中心没有农民生产队列';self.tip_until=now+6
        if now>=self.tip_until or not verified or not any(q.player==player and q.queue_verified and q.villager_count==0 for q in packet.get('queues',[])):self.tip=''
        self.assist_status.set('生产队列尚未适配：断农提醒等待数据，自动造农不可用' if not verified else
            ('请选择已识别的玩家' if player is None else f'提醒视角：玩家 {player} · 空队列持续 2 秒提醒，重复间隔 15 秒'))
    def extra_changed(self):
        self.last_telemetry=0;self.extra_tip='';self.extra_messages.clear();self.apply()
    def update_extra(self,packet,valid,now):
        flags={k:v.get() for k,v in self.extra_flags.items()}
        if not valid:
            self.side_panels=[];self.extra_tip='';self.extra_messages.clear()
            self.extra_status.set('等待有效对局；分数、人口、军事统计与指令来源尚未适配')
            return
        match=packet.get('match_key')
        if match!=self.extra_context:
            self.extra_context=match;self.extra_tip='';self.extra_messages.clear();self.last_telemetry=0
        if now-self.last_telemetry<.5:return
        self.last_telemetry=now;players=packet.get('telemetry',[])
        self.side_panels=panels(players,flags['scores'],flags['military'])
        local=next((p for p in players if p.player==packet.get('local_player')),None)
        if local and number(local.population_cap) and number(local.population_limit) and local.population_cap>=local.population_limit:
            if self.extra_tip.startswith('人口提醒：'):self.extra_tip=''
            self.extra_messages=deque((m for m in self.extra_messages if not m.startswith('人口提醒：')),maxlen=16)
        population=self.population_warning.update(match,local,now,flags['population'])
        if population:self.extra_messages.append(population)
        self.extra_messages.extend(self.military_warning.update(match,players,flags['intelligence']))
        if now>=self.extra_tip_until:
            self.extra_tip=self.extra_messages.popleft() if self.extra_messages else ''
            self.extra_tip_until=now+6
        # Current reader supplies identity/colour only. These values are not inferred.
        pending=[]
        if flags['evacuate']:pending.append('撤离待接通（缺指令来源、威胁与避难验证）')
        if flags['population']:pending.append('人口提醒：按现人口，剩余 ≤5；达到最终上限不提醒')
        if flags['scores']:pending.append('分数：游戏状态数据')
        if flags['military']:pending.append('军数：存活军事类型（含侦察兵）；军值：游戏 ArmyValue 资源和')
        if flags['intelligence']:pending.append('军情：敌方军数超过 25/50/100 时提醒')
        if packet.get('assistance_errors'):pending.append('部分辅助数据暂不可用：'+packet['assistance_errors'][0])
        self.extra_status.set('；'.join(pending) if pending else '新增辅助已关闭')
    def tick(self):
        if self.closing:return
        try:
            packet,status=self.sampler.snapshot();self.packet=packet;self.status.set(status)
            now=time.perf_counter()
            if self.names.pending and now-self.last_name_save>=3:
                self.last_name_save=now
                try:self.names.save()
                except (OSError,ValueError) as e:
                    self.names.error=str(e);log.warning('Name configuration: %s',e)
            valid=packet and now-packet['time']<.5 and now-packet['entity_time']<max(1,packet['interval']/1000*3)
            self.update_assistance(packet,valid,now)
            self.update_extra(packet,valid,now)
            if not valid:
                self.overlay.hide();self.stats['visible'].set('0')
                if self.table.get_children():self.table.delete(*self.table.get_children())
                for key in ('units','raw','read'):self.stats[key].set('—')
            else:
                entities=self.filtered(packet['entities'])
                if now-self.last_window>1 or self.target_pid!=packet['pid']:
                    self.target=game_window(packet['pid']);self.target_pid=packet['pid'];self.last_window=now
                rect=client_rect(self.target);labels=[]
                if rect and rect[2]>0 and rect[3]>0:
                    for e in entities:
                        projected=project(e.position,packet['camera'],rect[2],rect[3])
                        if projected and 0<=projected[0]<rect[2] and 0<=projected[1]<rect[3]:
                            text=self.names.display(e.blueprint) if self.labelstyle.get()!='完整蓝图名称' else e.blueprint
                            labels.append((e.id,projected[0],projected[1],text,e.color))
                self.visible=len(labels)
                if rect and (self.enabled.get() or self.tip or self.extra_tip or self.side_panels) and U.GetForegroundWindow()==self.target and not U.IsIconic(self.target):
                    self.overlay.draw(rect,labels if self.enabled.get() else [],getattr(self,'render_font',14),self.extra_tip or self.tip,self.side_panels,getattr(self,'render_score_font',11),getattr(self,'render_military_font',11))
                else:self.overlay.hide()
                if now-self.last_table>=.5:
                    self.names.observe(e.blueprint for e in packet['entities'])
                    self.last_table=now;self.refresh_table(entities)
                    options=['全部玩家']+[f'玩家 {n}' for n in sorted({e.player for e in packet['entities'] if e.player})]
                    if any(e.player==0 for e in packet['entities']):options.append('中立')
                    self.player_combo.configure(values=options)
                    self.stats['units'].set(str(len(entities)));self.stats['raw'].set(str(packet['count']))
                    self.stats['read'].set(f"{packet['ms']:.1f} / {packet['median']:.1f} ms")
                    self.stats['visible'].set(str(len(labels)))
                    self.status.set(f"已连接 · PID {packet['pid']} · 版本 {packet['version']} · 跳过异常实体 {packet['errors']}")
        except Exception as e:
            log.exception('UI refresh');self.status.set(f'显示错误: {e}');self.overlay.hide()
        self.root.after(33,self.tick)
    def export(self):
        packet=self.packet
        if not packet:messagebox.showinfo('暂无数据','请先连接运行中的对局。');return
        path=filedialog.asksaveasfilename(title='保存对局快照',defaultextension='.json',filetypes=[('JSON 快照','*.json'),('CSV 表格','*.csv')],initialfile=time.strftime('aoe4-snapshot-%Y%m%d-%H%M%S.json'))
        if not path:return
        rows=[dict(**asdict(e),display_name=self.names.display(e.blueprint)) for e in self.filtered(packet['entities'])]
        try:
            if path.lower().endswith('.csv'):
                with open(path,'w',encoding='utf-8-sig',newline='') as f:
                    writer=csv.DictWriter(f,fieldnames=['id','blueprint','display_name','player','color','position','address']);writer.writeheader();writer.writerows(rows)
            else:
                result={'build_sha256':packet['build_sha256'],'verified':packet['verified'],'pid':packet['pid'],'captured_at':time.strftime('%Y-%m-%dT%H:%M:%S%z'),
                    'entity_sample_age_ms':round((time.perf_counter()-packet['entity_time'])*1000,2),'camera':asdict(packet['camera']),
                    'raw_entity_count':packet['count'],'sample_ms':packet['ms'],'entities':rows}
                Path(path).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
            self.note.set('已导出：'+path)
        except OSError as e:messagebox.showerror('导出失败',str(e))
    def close(self):
        if self.name_editor and not self.name_editor.closed:
            self.name_editor.close()
            if not self.name_editor.closed:return
        if self.names.pending:
            try:self.names.save()
            except (OSError,ValueError) as e:log.warning('Name configuration: %s',e)
        self.closing=True;self.sampler.stop();self.overlay.hide();self.root.destroy()
    def run(self):self.root.mainloop()

if __name__=='__main__':
    try:App().run()
    except Exception:
        log.exception('Fatal startup error');raise
