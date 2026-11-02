"""Verified telemetry contracts and pure rules; no game input is emitted here."""
from dataclasses import dataclass,field
import math

@dataclass(frozen=True)
class PlayerTelemetry:
    player:int
    color:str='#bfc9d7'
    color_name:str=''
    enemy:bool|None=None
    population:float|None=None
    population_cap:float|None=None
    population_limit:float|None=None
    queued_population:float|None=None
    military_units:int|None=None
    military_population:float|None=None
    military_value:float|None=None
    scores:dict=field(default_factory=dict)

def number(value):
    return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value) and value>=0

def fmt(value):
    if not number(value):return '—'
    return str(int(value)) if value==int(value) else f'{value:.1f}'

def military_share(p):
    if not number(p.population) or not number(p.military_population) or p.population<=0 or p.military_population>p.population:return '—'
    return f'{p.military_population/p.population*100:.1f}%'

def ranked(players,key):
    return sorted((p for p in players if p.player>0),key=lambda p:(not number(key(p)),-key(p) if number(key(p)) else 0,p.player))

def panels(players,scores=False,military=False):
    result=[]
    if military:
        rows=[]
        for p in ranked(players,lambda p:p.military_value):
            rows.append((f'P{p.player}  价值 {fmt(p.military_value)}  现人口 {fmt(p.population)}\n军数 {fmt(p.military_units)}  军事人口 {fmt(p.military_population)}  占比 {military_share(p)}',p.color))
        result.append(('军事数据间谍 · ArmyValue 资源和排序',rows or [('等待玩家数据','#aebed2')]))
    if scores:
        rows=[]
        for p in ranked(players,lambda p:p.scores.get('总分')):
            fields=['军事','经济','社会','科技']+[k for k in p.scores if k not in ('总分','军事','经济','社会','科技')]
            detail='  '.join(f'{k} {fmt(p.scores.get(k))}' for k in fields)
            rows.append((f'P{p.player}  总分 {fmt(p.scores.get("总分"))}\n{detail}',p.color))
        result.append(('实时分数 · 按总分排序',rows or [('等待玩家数据','#aebed2')]))
    return result

class PopulationWarning:
    def __init__(self):self.context=None;self.last=-math.inf
    def update(self,match,p,now,enabled=True,margin=5):
        context=(match,p.player if p else None,enabled)
        if context!=self.context:self.context=context;self.last=-math.inf
        if not enabled or p is None:return None
        values=(p.population,p.population_cap,p.population_limit)
        if not all(number(v) for v in values):return None
        if p.population_cap>=p.population_limit:return None
        # A missing queue forecast still permits a warning from current population.
        queued=p.queued_population if number(p.queued_population) else 0
        if p.population_cap-p.population-queued>margin:
            self.last=-math.inf;return None
        if now-self.last<30:return None
        self.last=now
        return f'人口提醒：即将满人口（{fmt(p.population)}/{fmt(p.population_cap)}），请建造房屋'

class MilitaryWarning:
    def __init__(self):self.match=None;self.sent=set()
    def update(self,match,players,enabled=True):
        if match!=self.match:self.match=match;self.sent.clear()
        if not enabled:return []
        messages=[]
        for p in players:
            if p.player<=0 or p.enemy is not True or not number(p.military_units):continue
            crossed=[n for n in (25,50,100) if p.military_units>n and (p.player,n) not in self.sent]
            if not crossed:continue
            # One consolidated warning if several thresholds are crossed in one sample.
            self.sent.update((p.player,n) for n in crossed)
            color=p.color_name+'色' if p.color_name else p.color
            messages.append(f'注意，敌方{color}玩家 P{p.player} 爆兵{p.military_units}只，军事价值已达到：{fmt(p.military_value)}，军事分数已达到：{fmt(p.scores.get("军事"))}分')
        return messages

@dataclass(frozen=True)
class EvacuationObservation:
    villager:int
    owner:int
    verified:bool=False
    is_villager:bool=False
    threatening_players:tuple=()
    manual_attack:bool|None=None
    refuge:int|None=None
    safe_route:bool=False
    refuge_capacity:int=0
    already_safe:bool=False

class EvacuationPlanner:
    """Produces proposals only. Route/capacity/order origin must be verified.

    Planner reserves slots for pending proposals. User-issued attack orders
    invalidate pending proposals; executor must recheck newest intent before acting.
    """
    def __init__(self):self.context=None;self.pending={}
    def plan(self,match,local,observations,*,enabled,fresh,foreground,paused):
        context=(match,local)
        if context!=self.context or not enabled:self.context=context;self.pending.clear()
        if not enabled or match is None or local is None or not fresh or not foreground or paused:return []
        observed={v.villager:v for v in observations}
        for uid in list(self.pending):
            v=observed.get(uid)
            if v is None or v.already_safe or v.manual_attack is not False:self.pending.pop(uid,None)
        reserved={}
        for dest in self.pending.values():reserved[dest]=reserved.get(dest,0)+1
        proposals=[]
        for v in observations:
            threats=[p for p in v.threatening_players if p>0 and p!=local]
            if not(v.verified and v.is_villager and v.owner==local and threats and v.manual_attack is False):continue
            if v.already_safe or v.villager in self.pending or not v.safe_route or v.refuge is None:continue
            if reserved.get(v.refuge,0)>=v.refuge_capacity:continue
            self.pending[v.villager]=v.refuge;reserved[v.refuge]=reserved.get(v.refuge,0)+1
            proposals.append((v.villager,v.refuge))
        return proposals
