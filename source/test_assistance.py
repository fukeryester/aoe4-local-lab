import unittest
from types import SimpleNamespace
from assistance import IdleReminder,TownCenterQueue,exclude_local

class AssistanceTests(unittest.TestCase):
    def test_filter_identity_and_unknown(self):
        entities=[SimpleNamespace(player=p) for p in (0,1,2,3)]
        self.assertEqual([e.player for e in exclude_local(entities,True,2)],[0,1,3])
        self.assertEqual(exclude_local(entities,True,None),entities)
    def test_unknown_and_other_player_do_not_alert(self):
        r=IdleReminder()
        queues=[TownCenterQueue(1,1,None),TownCenterQueue(2,1,0,False),TownCenterQueue(3,2,0,True)]
        self.assertEqual(r.update('m',1,queues,0),[])
        self.assertEqual(r.update('m',1,queues,30),[])
    def test_debounce_repeat_and_recovery(self):
        r=IdleReminder();q=[TownCenterQueue(7,2,0,True)]
        self.assertEqual(r.update('m',2,q,0),[])
        self.assertEqual(r.update('m',2,q,2),[7])
        self.assertEqual(r.update('m',2,q,3),[])
        self.assertEqual(r.update('m',2,q,17),[7])
        r.update('m',2,[TownCenterQueue(7,2,1,True)],18)
        self.assertEqual(r.update('m',2,q,19),[])
    def test_switch_disable_and_destroy_clear_state(self):
        r=IdleReminder();q=[TownCenterQueue(7,2,0,True)]
        r.update('m',2,q,0)
        self.assertEqual(r.update('new',2,q,20),[])
        r.update('new',2,[],30)
        self.assertEqual(r.update('new',2,q,40),[])
        r.update('new',2,q,41,False)
        self.assertEqual(r.update('new',2,q,50),[])
    def test_multiple_centres(self):
        r=IdleReminder();q=[TownCenterQueue(7,2,0,True),TownCenterQueue(8,2,0,True)]
        r.update('m',2,q,0)
        self.assertEqual(r.update('m',2,q,2),[7,8])


from assistance import AutoVillagerPlanner,ProductionObservation
class AutoPlannerTests(unittest.TestCase):
    def plan(self,p,centres,**overrides):
        args=dict(enabled=True,foreground=True,fresh=True,paused=False,budget=1)
        args.update(overrides)
        return p.propose('match',2,centres,**args)
    def test_only_local_verified_trainable_centres(self):
        p=AutoVillagerPlanner()
        rows=[ProductionObservation(1,1,0,True,True),ProductionObservation(2,2,None,True,True),ProductionObservation(3,2,0,False,True),ProductionObservation(4,2,0,True,False)]
        self.assertIsNone(self.plan(p,rows))
    def test_waits_for_feedback_before_next_centre(self):
        p=AutoVillagerPlanner();rows=[ProductionObservation(i,2,0,True,True) for i in (1,2)]
        self.assertEqual(self.plan(p,rows),1)
        self.assertIsNone(self.plan(p,rows))
        rows[0]=ProductionObservation(1,2,1,True,True)
        self.assertEqual(self.plan(p,rows),2)
    def test_focus_pause_resources_and_stale_snapshot(self):
        rows=[ProductionObservation(1,2,0,True,True)]
        for args in ({'foreground':False},{'paused':True},{'fresh':False},{'budget':0},{'enabled':False}):
            self.assertIsNone(self.plan(AutoVillagerPlanner(),rows,**args))
    def test_rejected_command_not_retried(self):
        p=AutoVillagerPlanner();rows=[ProductionObservation(1,2,0,True,True)]
        self.assertEqual(self.plan(p,rows),1);p.rejected(1)
        self.assertIsNone(self.plan(p,rows))
    def test_new_match_clears_pending(self):
        p=AutoVillagerPlanner();rows=[ProductionObservation(1,2,0,True,True)]
        self.plan(p,rows)
        self.assertEqual(p.propose('new',2,rows,enabled=True,foreground=True,fresh=True,paused=False,budget=1),1)

if __name__=='__main__':unittest.main()
