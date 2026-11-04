"""Read-only auxiliary profile for the hash-gated 17.0.12260 reader.

Offsets follow Game_GetLocalPlayerID and Entity_GetProductionQueueItem.
Unrecognised extensions/items yield an unknown observation, never an empty queue.
"""
import math
import struct
from assistance import TownCenterQueue
from telemetry import PlayerTelemetry

SCORE_NAMES={'total_score':'总分','military_score':'军事','economy_score':'经济','society_score':'社会','technology_score':'科技'}


def army_statistics(reader):
    """Same player-stat records used by the game's ArmyValue UI binding.

    Resource vector is current army value, not cumulative military score.
    Military population is the game's modifier-aware accumulated statistic.
    """
    p=reader.p;base=reader.base
    client=p.u64(p.u64(base+0x7ceada8)+0x330)
    wrapper=p.u64(client+0x238);manager=p.u64(wrapper)
    if p.u64(manager)!=base+0x63e8820:raise ValueError('Unknown statistics manager')
    header=p.read(manager+0xb0,16);sentinel,count=struct.unpack('<QQ',header)
    if not 1<=count<=16:raise ValueError('Invalid statistics player count')
    registry=base+0x885d1a0
    start,end=struct.unpack('<QQ',p.read(registry+0x2e8,16))
    if end<start or (end-start)%48 or not 1<=(end-start)//48<=10:raise ValueError('Invalid resource registry')
    resources=(end-start)//48
    stack=[p.u64(sentinel+8)];seen=set();result={}
    while stack:
        node=stack.pop()
        if node==sentinel:continue
        if node in seen or len(seen)>=count:raise ValueError('Statistics tree changed')
        seen.add(node);row=p.read(node,0x28+0x73c)
        if row[0x19]:raise ValueError('Invalid statistics node')
        pid=struct.unpack_from('<I',row,0x20)[0]
        if pid in result:raise ValueError('Duplicate statistics player')
        costs=struct.unpack_from('<'+'f'*resources,row,0x28+0x2c4)
        population=struct.unpack_from('<I',row,0x28+0x734)[0]
        if not all(math.isfinite(v) and 0<=v<=1e9 for v in costs) or population>100000:raise ValueError('Invalid army statistics')
        result[pid]=(sum(costs),population)
        stack.extend((struct.unpack_from('<Q',row)[0],struct.unpack_from('<Q',row,16)[0]))
    if len(seen)!=count or p.read(manager+0xb0,16)!=header or p.u64(wrapper)!=manager:raise ValueError('Statistics changed during read')
    return result


def registry(reader,delta):
    cache=getattr(reader,'aux_registry',{})
    if delta in cache:return cache[delta]
    p=reader.p;a=reader.base+0x885d1a0+delta;header=p.read(a,16);start,end=struct.unpack('<QQ',header)
    if end<start or (end-start)%48 or (end-start)//48>8192:raise ValueError('Invalid registry')
    entries=p.read(start,end-start);result={}
    for i in range((end-start)//48):
        row=entries[i*48:(i+1)*48];length,capacity=struct.unpack_from('<QQ',row,24)
        if not 0<length<=1024 or capacity<length:raise ValueError('Invalid registry name')
        ptr=struct.unpack_from('<Q',row,8)[0] if capacity>15 else start+i*48+8
        name=p.read(ptr,length).decode('utf-8')
        result[name]=i
    if p.read(a,16)!=header:raise ValueError('Registry changed')
    cache[delta]=result;reader.aux_registry=cache
    return result


def player_scores(reader,player):
    p=reader.p;indices=registry(reader,0x708);state=player+0x308
    descriptor=p.u64(state+0x18);count=p.u64(descriptor+0x20)
    if count>8192:raise ValueError('Invalid state-model size')
    offsets=p.u64(descriptor+0x18) or descriptor+0x30;data=reader.arena+p.u32(state+0x20)
    scores={}
    for name,label in SCORE_NAMES.items():
        index=indices.get(name)
        if index is None or index>=count:continue
        offset=p.u64(offsets+index*8)
        if offset==0xffffffffffffffff:continue
        if offset>1000000:raise ValueError('Invalid state-model offset')
        value=struct.unpack('<f',p.read(data+offset,4))[0]
        if not math.isfinite(value) or not 0<=value<1e10:raise ValueError('Invalid score')
        scores[label]=value
    return scores


def military_counts(reader,entities):
    p=reader.p;index=registry(reader,0xa8).get('military')
    if index is None:raise ValueError('Missing military category')
    component=p.u32(reader.base+0x7903a38)
    if component>1024:raise ValueError('Invalid type component')
    counts={slot:0 for slot,_ in reader.players.values()};cache={}
    for e in entities:
        if e.player not in counts or not e.blueprint.startswith('unit_'):continue
        # Entity_IsAlive excludes killed entities still present in the world table.
        if p.u32(e.address+0xd8)&0x410!=0x10:continue
        bp=p.u64(e.address+0x38)
        if reader.name(bp)!=e.blueprint or p.u32(e.address+0xa0)!=e.id:raise ValueError('Entity changed')
        if bp not in cache:
            if p.u32(bp+0x64)!=0x130000:raise ValueError('Unexpected entity blueprint')
            type_data=p.u64(p.u64(p.u64(bp+0x140))+component*8)
            cache[bp]=bool(p.u64(type_data+0x18+(index//64)*8)&(1<<(index%64)))
        if cache[bp]:counts[e.player]+=1
    return counts


def relationships(reader,local):
    p=reader.p;indices={reader.players[pid][0]:p.u32(reader.arena+off+12) for off,pid in reader.player_offsets.items() if pid in reader.players}
    if local not in indices:return {}
    if any(i>=16 for i in indices.values()):raise ValueError('Invalid diplomacy index')
    diplomacy=reader.decode(p.u64(reader.world+0x308));row=p.read(diplomacy+0x40+indices[local]*16,16)
    return {slot:(row[index]==1 if row[index] in (1,2,3) else None) for slot,index in indices.items()}


def modified_value(reader,player,value,descriptor):
    """Scalar path of 0x2215630/0x2214190, including accumulated modifiers."""
    p=reader.p;base=reader.base
    index=(((p.u64(base+descriptor+8)-0x56a537c05d0681e4)&0xffffffffffffffff)^0xed9318d5daf7db22)&0xffffffff
    if index>4096:raise ValueError('Attribute index exceeds bounds')
    root=p.u64(p.u64(base+0x8640d68))
    if p.u32(reader.arena+p.u32(root+0x64)+index*4)==0:return value
    table=reader.arena+p.u32(player+0x300);secondary=p.u64(base+0x85f19c0)
    slot=p.read(secondary+p.u32(table)+index,1)[0]
    if slot==255:return value
    address=secondary+p.u32(table+12)+slot*52
    raw=p.read(address,28)
    multiply,add,percent,scale,_,override=struct.unpack_from('<6f',raw)
    if not all(math.isfinite(v) for v in (multiply,add,percent,scale,override)):raise ValueError('Invalid modifier')
    if raw[24]:return override
    return (value+add)*((multiply if raw[25] else 1)+scale)*(1+percent)


def population_capacity(reader,player):
    raw=reader.p.read(player+0x460,40)
    cap=modified_value(reader,player,struct.unpack_from('<f',raw)[0],0x8640b58)
    limit=modified_value(reader,player,struct.unpack_from('<f',raw,12)[0],0x8640bf8)
    cap=min(cap,limit)
    if raw[36:40]!=b'\xff\xff\x7f\x7f':cap=struct.unpack_from('<f',raw,36)[0]
    if not all(math.isfinite(v) and 0<=v<=100000 for v in (cap,limit)):raise ValueError('Invalid population capacity')
    return cap,limit


def local_player(reader):
    p=reader.p
    root=p.u64(reader.base+0x7ceada8)
    client=p.u64(root+0x330)
    pid=p.u32(client+0x154)
    if pid not in reader.player_offsets.values():return None
    return reader.players.get(pid,(None,None))[0]


def production_names(reader,entity):
    p=reader.p;base=reader.base;arena=reader.arena;a=entity.address
    before=p.read(a+0x38,0x70)
    if struct.unpack_from('<I',before,0x68)[0]!=entity.id:raise ValueError('Entity changed')
    if reader.name(struct.unpack_from('<Q',before)[0])!=entity.blueprint:raise ValueError('Blueprint changed')
    if p.u64(p.u64(a)+0xb0)!=base+0x1f48a80:raise ValueError('Unknown production getter')
    kind=struct.unpack_from('<H',before,0x14)[0]
    if kind>4096:raise ValueError('Unknown entity type')
    index=p.read(base+0x7ceb197+kind*128,1)[0]
    if index==255:raise ValueError('No production extension')
    secondary=p.u64(base+0x85f19c0)
    record=secondary+struct.unpack_from('<I',before,8)[0]+index*24
    raw=p.read(record,24)
    if not raw[16]&1:raise ValueError('Inactive production extension')
    pool=struct.unpack_from('<I',raw)[0];value=struct.unpack_from('<Q',raw,8)[0]
    if pool>8 or not value:raise ValueError('Invalid extension handle')
    extension=value if pool==8 else p.u64(base+0x85f1990+pool*16)+(value&0xffffffff)
    data=arena+p.u32(extension+0x54)
    header=p.read(data+0x40,8);offset,count=struct.unpack('<II',header)
    if count>256:raise ValueError('Production queue exceeds bounds')
    entries=p.read(arena+offset,count*144) if count else b''
    names=[]
    for i in range(count):
        obj=arena+struct.unpack_from('<I',entries,i*144+0x88)[0]
        vtable=p.u64(obj)
        if p.u64(vtable+8)!=base+0x25fc840 or p.u64(vtable+16)!=base+0x25fe370:
            raise ValueError('Unverified production item type')
        names.append(reader.name(p.u64(obj+0x10)))
    if p.read(data+0x40,8)!=header or (count and p.read(arena+offset,count*144)!=entries):
        raise ValueError('Production queue changed during read')
    after=p.read(a+0x38,0x70)
    if after[:8]!=before[:8] or after[0x68:0x6c]!=before[0x68:0x6c]:raise ValueError('Entity changed')
    if p.u64(base+0x85f1990)!=arena or p.u64(base+0x85f19c0)!=secondary:raise ValueError('Arena changed')
    return names


def snapshot(reader,entities):
    errors=[]
    try:local=local_player(reader)
    except (OSError,ValueError,struct.error) as e:local=None;errors.append(str(e))
    queues=[]
    for entity in entities:
        if not entity.blueprint.startswith('building_town_center_'):continue
        try:
            if reader.p.u32(entity.address+0xd8)&0x410!=0x10:continue
            names=production_names(reader,entity)
            queues.append(TownCenterQueue(entity.id,entity.player,sum(n.startswith('unit_villager_') for n in names),True))
        except (OSError,ValueError,struct.error) as e:
            queues.append(TownCenterQueue(entity.id,entity.player,None,False));errors.append(str(e))
    populations={};capacities={};scores={}
    try:army=army_statistics(reader)
    except (OSError,ValueError,struct.error) as e:army={};errors.append(str(e))
    try:counts=military_counts(reader,entities)
    except (OSError,ValueError,struct.error) as e:counts={};errors.append(str(e))
    try:enemies=relationships(reader,local)
    except (OSError,ValueError,struct.error) as e:enemies={};errors.append(str(e))
    for offset,pid in reader.player_offsets.items():
        try:
            a=reader.arena+offset
            current=struct.unpack('<f',reader.p.read(a+0x454,4))[0]
            adjustment=struct.unpack('<f',reader.p.read(a+0x490,4))[0]
            population=current+adjustment
            if not math.isfinite(population) or not 0<=population<=100000:raise ValueError('Invalid population')
            populations[pid]=population
        except (OSError,ValueError,struct.error) as e:errors.append(str(e))
        try:capacities[pid]=population_capacity(reader,reader.arena+offset)
        except (OSError,ValueError,struct.error) as e:errors.append(str(e))
        try:scores[pid]=player_scores(reader,reader.arena+offset)
        except (OSError,ValueError,struct.error) as e:errors.append(str(e))
    if reader.p.u64(reader.base+0x85f1990)!=reader.arena or reader.decode(reader.p.u64(reader.base+0x863f348))!=reader.world:
        raise ValueError('Match changed during auxiliary read')
    return {'local_player':local,'queues':queues,
            'queue_verified':any(q.queue_verified for q in queues),
            'telemetry':[PlayerTelemetry(slot,color,color_name={'#ff3b30':'红','#00e000':'绿'}.get(color,''),enemy=enemies.get(slot),population=populations.get(pid),population_cap=capacities.get(pid,(None,None))[0],population_limit=capacities.get(pid,(None,None))[1],scores=scores.get(pid,{}),military_units=counts.get(slot),military_value=army.get(pid,(None,None))[0],military_population=army.get(pid,(None,None))[1]) for pid,(slot,color) in reader.players.items()],
            'assistance_errors':errors}
