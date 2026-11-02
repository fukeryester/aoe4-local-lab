import copy
import tkinter as tk
from tkinter import ttk,filedialog,messagebox,simpledialog
from unit_names import default_name,checked,import_csv,export_csv

class NameEditor:
    def __init__(self,app,selected=None):
        self.app=app;self.store=app.names;self.base=copy.deepcopy(self.store.rows);self.rows=copy.deepcopy(self.base)
        self.cell=None;self.dirty=False;self.closed=False
        self.win=tk.Toplevel(app.root);self.win.title('单位名称配置');self.win.geometry('1120x670');self.win.minsize(850,500)
        self.win.configure(bg='#101722');self.win.protocol('WM_DELETE_WINDOW',self.close)
        outer=ttk.Frame(self.win,padding=20);outer.pack(fill='both',expand=True)
        ttk.Label(outer,text='单位名称配置',font=('Microsoft YaHei UI',19,'bold')).pack(anchor='w')
        ttk.Label(outer,text='双击“自定义名称”或“备注”编辑；Enter / Tab 完成编辑并跳到下一行。清空名称恢复默认。',style='Muted.TLabel').pack(anchor='w',pady=(6,4))
        ttk.Label(outer,text='完整蓝图精确匹配：不同文明、等级可分别配置，队友与对手的同一蓝图共用名称。',style='Muted.TLabel').pack(anchor='w',pady=(0,12))
        tools=ttk.Frame(outer);tools.pack(fill='x',pady=(0,12))
        ttk.Button(tools,text='收集当前对局',command=self.collect).pack(side='left')
        ttk.Button(tools,text='新增蓝图',command=self.add_row).pack(side='left',padx=(8,0))
        ttk.Button(tools,text='导入 CSV',command=self.import_table).pack(side='left',padx=8)
        ttk.Button(tools,text='导出 CSV',command=self.export_table).pack(side='left')
        ttk.Button(tools,text='保存并应用',command=self.save).pack(side='right')
        search=ttk.Frame(outer);search.pack(fill='x',pady=(0,10))
        ttk.Label(search,text='搜索').pack(side='left');self.query=tk.StringVar(value=selected or '')
        ttk.Entry(search,textvariable=self.query).pack(side='left',fill='x',expand=True,padx=8)
        ttk.Button(search,text='清除搜索',command=lambda:self.query.set('')).pack(side='left')
        self.query.trace_add('write',lambda *_:self.render())
        frame=ttk.Frame(outer);frame.pack(fill='both',expand=True)
        self.table=ttk.Treeview(frame,columns=('bp','default','custom','notes'),show='headings',height=10,selectmode='browse')
        for col,title,width in [('bp','蓝图名称（只读）',390),('default','默认名称（只读）',180),('custom','自定义名称（双击编辑）',210),('notes','备注（双击编辑）',220)]:
            self.table.heading(col,text=title);self.table.column(col,width=width,minwidth=100,stretch=True)
        sb=ttk.Scrollbar(frame,orient='vertical',command=self.scroll_rows);self.table.configure(yscrollcommand=sb.set)
        self.table.pack(side='left',fill='both',expand=True);sb.pack(side='right',fill='y')
        self.table.bind('<Double-1>',self.edit_clicked);self.table.bind('<F2>',lambda e:self.edit_selected())
        self.table.bind('<Return>',lambda e:self.edit_selected())
        self.table.bind('<MouseWheel>',lambda e:None if self.commit() else 'break')
        self.hint=tk.StringVar();ttk.Label(outer,textvariable=self.hint,wraplength=1050).pack(anchor='w',pady=(12,5))
        ttk.Label(outer,text='Excel 编辑方式：导出 CSV → 修改“自定义名称” → 导入 CSV → 保存并应用。导入只合并表中蓝图，不删除其他配置。',style='Muted.TLabel',wraplength=1050).pack(anchor='w')
        self.render()
        if self.store.error:self.hint.set('现有配置读取失败，原文件已保留：'+self.store.error)
    def render(self):
        if self.closed:return
        if self.cell is not None and not self.commit():return
        selected=self.table.selection();old=selected[0] if selected else None
        self.table.delete(*self.table.get_children());q=self.query.get().strip().casefold();count=0
        for bp,row in sorted(self.rows.items()):
            if q and q not in ' '.join([bp,default_name(bp),row['custom_name'],row['notes']]).casefold():continue
            self.table.insert('','end',iid=bp,values=(bp,default_name(bp),row['custom_name'],row['notes']));count+=1
        if old and self.table.exists(old):self.table.selection_set(old)
        elif self.table.get_children():self.table.selection_set(self.table.get_children()[0])
        self.hint.set(f'显示 {count} / {len(self.rows)} 种蓝图'+(' · 有未保存修改' if self.dirty else ' · 已保存的自定义名称优先于默认名称') if self.rows else '暂无已收集的蓝图。进入对局后点击“收集当前对局”，或通过“新增蓝图”及 CSV 预先配置。')
    def scroll_rows(self,*args):
        if self.commit():self.table.yview(*args)
    def add_row(self):
        if not self.commit():return
        value=simpledialog.askstring('新增蓝图','请输入完整蓝图名称（可从主列表的真实蓝图名称获取）：',parent=self.win)
        if value is None:return
        try:bp,row=checked(value)
        except ValueError as e:messagebox.showerror('蓝图名称无效',str(e),parent=self.win);return
        if bp not in self.rows:self.rows[bp]=row;self.dirty=True
        self.query.set(bp);self.render();self.edit(bp,'#3')
    def edit_clicked(self,event):
        bp=self.table.identify_row(event.y);col=self.table.identify_column(event.x)
        if bp and col in ('#3','#4'):self.edit(bp,col)
    def edit_selected(self):
        selected=self.table.selection()
        if selected:self.edit(selected[0],'#3')
        return 'break'
    def edit(self,bp,col):
        if self.cell is not None and not self.commit():return
        self.table.see(bp);self.table.selection_set(bp);self.table.update_idletasks();box=self.table.bbox(bp,col)
        if not box:return
        key='custom_name' if col=='#3' else 'notes';entry=tk.Entry(self.table,font=('Microsoft YaHei UI',10),bg='#fff7db',fg='#152336',relief='solid',bd=1)
        entry.insert(0,self.rows[bp][key]);entry.place(x=box[0],y=box[1],width=box[2],height=box[3]);entry.focus_set();entry.select_range(0,'end')
        self.cell=(entry,bp,key,col)
        entry.bind('<Return>',lambda e:self.next_row());entry.bind('<Tab>',lambda e:self.next_row())
        entry.bind('<Escape>',lambda e:self.cancel_cell());entry.bind('<FocusOut>',lambda e:self.commit())
    def commit(self):
        if self.cell is None:return True
        entry,bp,key,col=self.cell;row=dict(self.rows[bp]);row[key]=entry.get()
        try:_,value=checked(bp,**row)
        except ValueError as e:
            self.hint.set(str(e));return False
        self.cell=None;entry.destroy()
        if value!=self.rows[bp]:self.rows[bp]=value;self.dirty=True
        if self.table.exists(bp):self.table.item(bp,values=(bp,default_name(bp),value['custom_name'],value['notes']))
        self.hint.set('修改暂存于表格，点击“保存并应用”后立即更新标签和主列表。' if self.dirty else '当前行未改变')
        return True
    def cancel_cell(self):
        if self.cell:entry=self.cell[0];self.cell=None;entry.destroy()
        self.table.focus_set();return 'break'
    def next_row(self):
        if self.cell is None:return 'break'
        _,bp,_,col=self.cell
        if not self.commit():return 'break'
        nxt=self.table.next(bp)
        if nxt:self.edit(nxt,col)
        else:self.table.focus_set()
        return 'break'
    def collect(self):
        if not self.commit():return
        packet=self.app.packet
        if not packet:self.hint.set('当前没有有效对局数据；已有名称仍可编辑。');return
        self.store.observe(e.blueprint for e in packet['entities']);before=len(self.rows)
        for bp,row in self.store.rows.items():self.rows.setdefault(bp,dict(row))
        self.render();self.hint.set(f'已加入 {len(self.rows)-before} 种新蓝图；配置会按类型保留到后续对局。')
    def import_table(self):
        if not self.commit():return
        path=filedialog.askopenfilename(parent=self.win,title='导入名称配置 CSV',filetypes=[('CSV 名称配置','*.csv')])
        if not path:return
        try:incoming=import_csv(path)
        except (OSError,ValueError,UnicodeError) as e:messagebox.showerror('导入失败',str(e),parent=self.win);return
        changed=sum(self.rows.get(bp)!=row for bp,row in incoming.items());self.rows.update(incoming);self.dirty=self.dirty or bool(changed)
        self.query.set('');self.render();self.hint.set(f'已暂存导入 {len(incoming)} 行，其中 {changed} 行有变化。检查后点击“保存并应用”。')
    def export_table(self):
        if not self.commit():return
        path=filedialog.asksaveasfilename(parent=self.win,title='导出全部名称配置',defaultextension='.csv',initialfile='单位名称配置.csv',filetypes=[('CSV 名称配置','*.csv')])
        if not path:return
        try:export_csv(path,self.rows);self.hint.set(f'已导出全部 {len(self.rows)} 行（包含暂存修改）：{path}')
        except OSError as e:messagebox.showerror('导出失败',str(e),parent=self.win)
    def save(self):
        if not self.commit():return False
        changes={bp:row for bp,row in self.rows.items() if self.base.get(bp)!=row}
        try:self.store.save(changes,expected=self.base)
        except (OSError,ValueError) as e:messagebox.showerror('保存失败',str(e),parent=self.win);return False
        self.base=copy.deepcopy(self.store.rows);self.rows=copy.deepcopy(self.base);self.dirty=False
        self.app.labelstyle.set('自定义 / 默认名称');self.app.last_table=0
        self.render();self.hint.set('已保存并立即应用到画面标签、主列表和快照导出。');return True
    def close(self):
        if not self.commit():return
        if self.dirty:
            answer=messagebox.askyesnocancel('未保存修改','保存名称修改后关闭？',parent=self.win)
            if answer is None:return
            if answer and not self.save():return
        self.closed=True;self.win.destroy()
