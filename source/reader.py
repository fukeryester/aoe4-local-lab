"""AoE IV 17.0.12182.0: empirically traced read-only layout.

This profile is tied to the executable hash; no function is called inside the game.
Unknown or changing layouts raise errors, never return demo data.
"""
import hashlib,math,struct,time
from dataclasses import dataclass
from memory import Process,game_pids

BUILD_SHA256='4c99b868cbec98b2219e135908a31d03c64c7b71f2bbcf1469dab1d7c6df2c9f'
KEY=0x21790fdcf3f2dcc8
MASK=0xffffffffffffffff
def fnv32(n):
    h=0xcbf29ce484222325
    for v in struct.pack('<I',n):h=((h^v)*0x100000001b3)&MASK
    return h
def bounded(n,maximum,label):
    if not 0<=n<=maximum:raise ValueError(f'{label} 超出已验证范围: {n}')
    return n

@dataclass(frozen=True)
class Entity:
    id:int
    blueprint:str
    player:int
    color:str
    position:tuple
    address:int

@dataclass(frozen=True)
class Camera:
    eye:tuple
    target:tuple
    fov:float

def project(position,camera,width,height):
    """Perspective projection; y-up world. FOV convention verified in a live view."""
    def norm(v):
        length=math.sqrt(sum(x*x for x in v))
        if length<1e-7:raise ValueError('相机方向无效')
        return tuple(x/length for x in v)
    forward=norm(tuple(t-e for t,e in zip(camera.target,camera.eye)))
    right=norm((forward[2],0,-forward[0]))
    up=(forward[1]*right[2]-forward[2]*right[1],forward[2]*right[0]-forward[0]*right[2],forward[0]*right[1]-forward[1]*right[0])
    delta=tuple(v-e for v,e in zip(position,camera.eye));depth=sum(a*b for a,b in zip(delta,forward))
    if depth<=0.1:return None
    focal=height/(2*math.tan(math.radians(camera.fov)/2))
    x=width/2+sum(a*b for a,b in zip(delta,right))*focal/depth
    y=height/2-sum(a*b for a,b in zip(delta,up))*focal/depth
    if not (-50<=x<=width+50 and -50<=y<=height+50):return None
    return x,y,depth

class Reader:
    def __init__(self,pid=None):
        if pid is None:
            ids=game_pids()
            if len(ids)!=1:raise RuntimeError(f'需要唯一游戏进程，当前检测到 {len(ids)} 个')
            pid=ids[0]
        self.p=Process(pid)
        try:
            self.module=next(m for m in self.p.modules() if m['name'].lower()=='reliccardinal.exe')
            with open(self.module['path'],'rb') as f:actual=hashlib.file_digest(f,'sha256').hexdigest()
            if actual!=BUILD_SHA256:raise RuntimeError('游戏版本与已验证配置不符，停止读取。需要重新适配。')
            self.base=self.module['base'];self.names={};self.members=[];self.last_members=0;self.last_arena=None
            self.last_colors=0;self.players={};self.raw_count=0;self.errors=0;self.last_world=None
        except BaseException:self.p.close();raise
    def close(self):self.p.close()
    def decode(self,value):return self.arena+((value^KEY)&0xffffffff)
    def setup_world(self):
        self.arena=self.p.u64(self.base+0x85f0990)
        if self.arena!=self.last_arena:self.last_members=0;self.last_colors=0;self.last_arena=self.arena
        self.world=self.decode(self.p.u64(self.base+0x863e348))
        if self.world!=self.last_world:self.last_members=0;self.last_colors=0;self.last_world=self.world
        players=self.decode(self.p.u64(self.world+0x140));n=bounded(self.p.u32(players+0x10),16,'玩家数')
        if n<1:raise RuntimeError('尚未进入可读取的对局')
        offsets=struct.unpack('<'+'I'*n,self.p.read(self.arena+self.p.u32(players+0xc),4*n))
        self.player_offsets={o:self.p.u32(self.arena+o+8) for o in offsets}
    def palette(self):
        p=self.p;root=p.u64(self.base+0x85ee450);table=p.u64(root+0x280);mask=p.u64(root+0x298);sent=p.u64(root+0x270)
        first,node=struct.unpack('<QQ',p.read(table+(fnv32(0x320000)&mask)*16,16))
        for _ in range(128):
            if node==sent:raise RuntimeError('未找到颜色数据')
            if p.u32(node+0x10)==0x320000:break
            if node==first:raise RuntimeError('未找到颜色数据')
            node=p.u64(node+8)
        else:raise RuntimeError('颜色容器遍历上限')
        bp=p.u64(p.u64(node+0x18))
        if p.u32(bp+0x5c)!=0x320000:raise RuntimeError('颜色类型不匹配')
        index=bounded(p.u32(self.base+0x792329c),1024,'颜色索引')
        palette=p.u64(p.u64(p.u64(bp+0x138))+index*8)
        start,end=struct.unpack('<QQ',p.read(palette+0x20,16));n=bounded((end-start)//8,64,'颜色数量')
        raw=p.read(start,n*8)
        return ['#%02x%02x%02x'%(raw[i*8+2],raw[i*8+1],raw[i*8]) for i in range(n)]
    def colors(self):
        p=self.p;palette=self.palette();root=p.u64(p.u64(self.base+0x8672338))
        slots=p.u64(root+0x1c30) or root+0x1c48;n=bounded(p.u64(root+0x1c38),32,'大厅玩家数')
        config=p.u64(root+0x10) or root+0x28;config_count=bounded(p.u64(root+0x18),32,'大厅配置数')
        out={}
        for i in range(n):
            row=p.read(slots+i*0x108,12);slot,_,pid=struct.unpack('<III',row)
            if slot>=config_count:continue
            default,_,selected=struct.unpack('<iii',p.read(config+slot*0x1c0+0x60,12));idx=selected if selected>=0 else default
            if not 0<=idx<len(palette):raise RuntimeError('玩家所选颜色索引无效')
            out[pid]=(slot+1,palette[idx])
        self.players=out
    def name(self,bp):
        if bp not in self.names:
            ptr=(self.p.u64(bp+0x18)-0x401b56464badd2df+0x6e9f8c4cebc17703)&MASK
            raw=self.p.read(ptr,32);n,cap=struct.unpack_from('<QQ',raw,16);bounded(n,1024,'蓝图名称长度')
            if cap<n:raise ValueError('蓝图字符串容量无效')
            sp=struct.unpack_from('<Q',raw)[0] if cap>15 else ptr
            name=self.p.read(sp,n).split(b'\0')[0].decode('utf-8',errors='replace')
            if not name or any(ord(c)<32 for c in name):raise ValueError('蓝图名称无效')
            self.names[bp]=name
        return self.names[bp]
    def membership(self):
        p=self.p;mgr=self.decode(p.u64(self.world+0x1b8));header=p.read(mgr+0x720,8);arr,n=struct.unpack('<II',header)
        bounded(n,100000,'实体数量');offsets=struct.unpack('<'+'I'*n,p.read(self.arena+arr,4*n)) if n else []
        found=[];errors=0
        for off in offsets:
            try:
                raw=p.read(self.arena+off,0xb0);bp=struct.unpack_from('<Q',raw,0x38)[0];name=self.name(bp)
                # Weapon/projectile/helper entities have no independently labelled game unit.
                if name.startswith(('unit_','building_','gaia_')):
                    found.append((off,struct.unpack_from('<I',raw,0xa0)[0],bp,name))
            except (OSError,ValueError,struct.error):errors+=1
        if p.read(mgr+0x720,8)!=header or p.u64(self.base+0x85f0990)!=self.arena:raise RuntimeError('实体表正在切换，等待下一次采样')
        self.members=found;self.raw_count=n;self.errors=errors
    def entities(self,include_neutral=False):
        now=time.perf_counter();self.setup_world()
        if now-self.last_colors>=1:self.colors();self.last_colors=now
        if now-self.last_members>=0.5:self.membership();self.last_members=now
        result=[];failed=0
        for off,uid,bp,name in self.members:
            try:
                raw=self.p.read(self.arena+off,0xb0)
                if struct.unpack_from('<I',raw,0xa0)[0]!=uid or struct.unpack_from('<Q',raw,0x38)[0]!=bp:continue
                owner=(struct.unpack_from('<Q',raw,0x70)[0]^KEY)&0xffffffff
                pid=self.player_offsets.get(owner)
                if pid is None:
                    if not include_neutral:continue
                    slot,color=0,'#bfc9d7'
                else:
                    if pid not in self.players:raise ValueError('玩家未匹配到大厅颜色')
                    slot,color=self.players[pid]
                position=struct.unpack_from('<fff',raw,0x2c)
                if not all(math.isfinite(x) and abs(x)<1e5 for x in position):continue
                result.append(Entity(uid,name,slot,color,position,self.arena+off))
            except (OSError,ValueError,struct.error):failed+=1
        if self.p.u64(self.base+0x85f0990)!=self.arena:raise RuntimeError('模拟内存快照已切换')
        return result,failed
    def camera(self):
        p=self.p;board=p.u64(self.base+0x7ce9ec0);r9=p.u64(board+0x30)
        a,c=struct.unpack('<II',p.read(r9-0x50,8));bucket=(fnv32(a)^fnv32(c))&p.u64(r9-0x18)
        table=p.u64(r9-0x30);first,node=struct.unpack('<QQ',p.read(table+bucket*16,16));sent=p.u64(r9-0x40)
        for _ in range(128):
            if node==sent:raise RuntimeError('没有活动相机')
            if struct.unpack('<II',p.read(node+0x10,8))==(a,c):break
            if node==first:raise RuntimeError('相机索引失效')
            node=p.u64(node+8)
        else:raise RuntimeError('相机容器遍历上限')
        raw=p.read(node+0x18+0x50,0x54)
        eye=struct.unpack_from('<fff',raw);target=struct.unpack_from('<fff',raw,0x1c);fov=struct.unpack_from('<f',raw,0x50)[0]
        if not all(math.isfinite(v) for v in (*eye,*target,fov)) or not 5<fov<150:raise ValueError('相机参数无效')
        return Camera(eye,target,fov)

if __name__=='__main__':
    import json
    from dataclasses import asdict
    r=Reader();start=time.perf_counter();entities,failed=r.entities();cam=r.camera()
    print(json.dumps({'pid':r.p.pid,'raw_entities':r.raw_count,'units':len(entities),'failed':failed,'camera':asdict(cam),'ms':(time.perf_counter()-start)*1000,'sample':[dict(**asdict(e),screen=project(e.position,cam,2560,1440)) for e in entities if e.blueprint.startswith(('unit_','building_town_center'))]},ensure_ascii=False,indent=2));r.close()
