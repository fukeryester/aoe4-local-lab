"""Exact blueprint-to-display-name mappings, persisted independently of the EXE."""
import csv,io,json,os,tempfile
from pathlib import Path

def default_name(blueprint):
    for marker,label in [('town_center','城镇中心'),('villager','村民'),('scout','侦察兵'),
        ('herdable_sheep','绵羊'),('mining_camp','采矿场'),('lumber_camp','伐木场'),
        ('lancastercastle','兰开斯特城堡'),('house','房屋'),('barracks','兵营'),
        ('archery_range','射箭军营'),('stable','马厩'),('econ_mill','磨坊')]:
        if marker in blueprint:return label
    return blueprint

def checked(blueprint,custom_name='',notes=''):
    if not all(isinstance(v,str) for v in (blueprint,custom_name,notes)):
        raise ValueError('蓝图名称、自定义名称和备注必须为文本')
    blueprint=blueprint.strip();custom_name=custom_name.strip();notes=notes.strip()
    if not blueprint or len(blueprint)>256 or any(c.isspace() for c in blueprint):
        raise ValueError('蓝图名称不能为空、包含空白或超过 256 字符')
    for label,value,limit in [('蓝图名称',blueprint,256),('自定义名称',custom_name,120),('备注',notes,500)]:
        if len(value)>limit or any(ord(c)<32 or ord(c)==127 for c in value):
            raise ValueError(f'{label}包含控制字符或超过 {limit} 字符')
    return blueprint,{'custom_name':custom_name,'notes':notes}

def import_csv(path):
    raw=Path(path).read_bytes()
    if len(raw)>5_000_000:raise ValueError('配置表不能超过 5 MB')
    try:text=raw.decode('utf-8-sig')
    except UnicodeDecodeError:text=raw.decode('gb18030')
    reader=csv.DictReader(io.StringIO(text,newline=''))
    aliases={'蓝图名称':'blueprint','真实蓝图名称':'blueprint','自定义名称':'custom_name','备注':'notes',
        '默认名称':'default_name','blueprint':'blueprint','custom_name':'custom_name','notes':'notes','default_name':'default_name'}
    headers=reader.fieldnames or []
    normalized=[aliases.get(h.strip(),h.strip()) for h in headers]
    if len(set(normalized))!=len(normalized):raise ValueError('CSV 存在重复列名')
    if not {'blueprint','custom_name'}.issubset(normalized):raise ValueError('CSV 必须包含“蓝图名称”和“自定义名称”两列')
    result={}
    for line,row in enumerate(reader,2):
        if None in row:raise ValueError(f'CSV 第 {line} 行列数多于表头')
        if all(not (v or '').strip() for v in row.values()):continue
        if any(v is None for v in row.values()):raise ValueError(f'CSV 第 {line} 行缺少单元格')
        values={aliases.get(k.strip(),k.strip()):v for k,v in row.items()}
        try:bp,value=checked(values.get('blueprint',''),values.get('custom_name',''),values.get('notes',''))
        except ValueError as e:raise ValueError(f'CSV 第 {line} 行：{e}') from e
        if bp in result:raise ValueError(f'CSV 第 {line} 行蓝图重复：{bp}')
        result[bp]=value
        if len(result)>20000:raise ValueError('配置表不能超过 20,000 行')
    return result

def export_csv(path,rows):
    with open(path,'w',encoding='utf-8-sig',newline='') as f:
        writer=csv.writer(f);writer.writerow(['蓝图名称','默认名称','自定义名称','备注'])
        for bp,value in sorted(rows.items()):writer.writerow([bp,default_name(bp),value['custom_name'],value['notes']])

class NameStore:
    def __init__(self,path):
        self.path=Path(path);self.rows={};self.pending=False;self.error=''
        try:self.rows=self._read()
        except (OSError,ValueError) as e:self.error=str(e)
    def _read(self):
        if not self.path.exists():return {}
        raw=self.path.read_bytes()
        if len(raw)>5_000_000:raise ValueError('名称配置超过 5 MB')
        payload=json.loads(raw.decode('utf-8'))
        if not isinstance(payload,dict) or payload.get('version')!=1 or not isinstance(payload.get('units'),dict):
            raise ValueError('名称配置格式不正确，原文件已保留')
        if len(payload['units'])>20000:raise ValueError('配置表超过 20,000 行')
        result={}
        for bp,value in payload['units'].items():
            if not isinstance(value,dict):raise ValueError('名称配置行必须为对象')
            key,row=checked(bp,value.get('custom_name',''),value.get('notes',''))
            if key in result:raise ValueError('配置包含重复蓝图名称')
            result[key]=row
        return result
    def observe(self,blueprints):
        added=0
        for bp in blueprints:
            if bp not in self.rows:
                bp,row=checked(bp);self.rows[bp]=row;added+=1
        self.pending=self.pending or bool(added)
        return added
    def display(self,blueprint):
        return self.rows.get(blueprint,{}).get('custom_name') or default_name(blueprint)
    def save(self,changes=None,expected=None):
        """Merge observed units with latest disk state; never silently replace bad data."""
        changes=changes or {};clean={}
        for bp,row in changes.items():
            key,value=checked(bp,row.get('custom_name',''),row.get('notes',''));clean[key]=value
        latest=self._read()
        if expected is not None:
            empty={'custom_name':'','notes':''}
            for bp,value in clean.items():
                actual=latest.get(bp,empty);before=expected.get(bp,empty)
                if actual!=before and actual!=value:
                    raise ValueError(f'{bp} 的配置已被其他窗口或程序修改，请重新打开配置表后再编辑')
        for bp in self.rows:latest.setdefault(bp,{'custom_name':'','notes':''})
        latest.update(clean)
        if len(latest)>20000:raise ValueError('配置表不能超过 20,000 行')
        self.path.parent.mkdir(parents=True,exist_ok=True)
        fd,tmp=tempfile.mkstemp(prefix='unit_names-',suffix='.tmp',dir=self.path.parent)
        try:
            with os.fdopen(fd,'w',encoding='utf-8',newline='\n') as f:
                json.dump({'version':1,'units':latest},f,ensure_ascii=False,indent=2);f.flush();os.fsync(f.fileno())
            os.replace(tmp,self.path)
        finally:
            if os.path.exists(tmp):os.unlink(tmp)
        self.rows=latest;self.pending=False;self.error=''

