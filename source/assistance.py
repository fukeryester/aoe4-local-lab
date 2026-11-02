"""Pure assistance state logic. Unknown observations never mean an empty queue."""
from dataclasses import dataclass

@dataclass(frozen=True)
class TownCenterQueue:
    entity_id:int
    player:int
    villager_count:int|None
    queue_verified:bool=False

class IdleReminder:
    def __init__(self,delay=2.0,repeat=15.0):
        self.delay=delay;self.repeat=repeat;self.since={};self.last={};self.context=None
    def reset(self):
        self.since.clear();self.last.clear();self.context=None
    def update(self,match,player,queues,now,enabled=True):
        context=(match,player)
        if not enabled or player is None:
            self.reset();return []
        if context!=self.context:
            self.reset();self.context=context
        idle={q.entity_id for q in queues if q.player==player and q.queue_verified and q.villager_count==0}
        for uid in self.since.keys()-idle:
            self.since.pop(uid,None);self.last.pop(uid,None)
        alerts=[]
        for uid in sorted(idle):
            self.since.setdefault(uid,now)
            if now-self.since[uid]>=self.delay and now-self.last.get(uid,float('-inf'))>=self.repeat:
                self.last[uid]=now;alerts.append(uid)
        return alerts

def exclude_local(entities,enabled,local_player):
    # Never guess the local player from colour, lowest slot or camera position.
    return [e for e in entities if not enabled or local_player is None or e.player!=local_player]

@dataclass(frozen=True)
class ProductionObservation:
    entity_id:int
    player:int
    villager_count:int|None
    can_train:bool=False
    verified:bool=False

class AutoVillagerPlanner:
    """Plans one command at a time; does not send input or call game functions.

    After a proposal, wait for confirmed queue feedback. Never retry an
    unacknowledged command automatically: the previous command may have succeeded.
    """
    def __init__(self):
        self.context=None;self.pending=None;self.failed=set()
    def reset(self):
        self.context=None;self.pending=None;self.failed.clear()
    def propose(self,match,local_player,centres,*,enabled,foreground,fresh,paused,budget):
        if not enabled or local_player is None or match is None:
            self.reset();return None
        context=(match,local_player)
        if context!=self.context:self.reset();self.context=context
        if not foreground or not fresh or paused:return None
        owned={c.entity_id:c for c in centres if c.player==local_player}
        self.failed.intersection_update(owned)
        if self.pending is not None:
            observation=owned.get(self.pending)
            if observation is None:
                self.pending=None
            elif observation.verified and observation.villager_count is not None and observation.villager_count>0:
                self.pending=None
            else:return None
        if budget<1:return None
        for uid,c in sorted(owned.items()):
            if uid not in self.failed and c.verified and c.villager_count==0 and c.can_train:
                self.pending=uid;return uid
        return None
    def rejected(self,entity_id):
        if self.pending==entity_id:
            self.pending=None;self.failed.add(entity_id)
