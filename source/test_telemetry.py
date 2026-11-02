import unittest
from dataclasses import replace
from telemetry import *

class TelemetryTests(unittest.TestCase):
    def test_sort_unknown_last_and_tie_stable(self):
        rows=[PlayerTelemetry(3,military_value=None),PlayerTelemetry(2,military_value=100),PlayerTelemetry(1,military_value=100)]
        self.assertEqual([p.player for p in ranked(rows,lambda p:p.military_value)],[1,2,3])
    def test_population_share_uses_population_not_headcount(self):
        p=PlayerTelemetry(1,population=100,military_units=10,military_population=30)
        self.assertEqual(military_share(p),'30.0%')
        self.assertEqual(military_share(replace(p,population=0)),'—')
    def test_unknown_and_invalid_are_not_zero(self):
        for x in (None,float('nan'),float('inf'),-1,True):self.assertEqual(fmt(x),'—')
    def test_score_fields_and_sorting(self):
        rows=[PlayerTelemetry(1,scores={'总分':10}),PlayerTelemetry(2,scores={'总分':20,'特殊':5})]
        group=panels(rows,scores=True)[0]
        self.assertIn('P2',group[1][0][0]);self.assertIn('特殊 5',group[1][0][0]);self.assertIn('社会 —',group[1][0][0])
    def test_population_queue_and_limit(self):
        r=PopulationWarning();p=PlayerTelemetry(1,population=30,population_cap=40,population_limit=200,queued_population=6)
        self.assertIsNotNone(r.update('m',p,0));self.assertIsNone(r.update('m',p,1))
        self.assertIsNone(r.update('m',replace(p,population_cap=200),100))
        self.assertIsNone(r.update('m',replace(p,queued_population=None),100))
    def test_population_recovery_and_new_match(self):
        r=PopulationWarning();p=PlayerTelemetry(1,population=38,population_cap=40,population_limit=200,queued_population=0)
        r.update('m',p,0);r.update('m',replace(p,population=20),1)
        self.assertIsNotNone(r.update('m',p,2))
        self.assertIsNotNone(r.update('new',p,3))
    def test_population_without_forecast_uses_current_only(self):
        p=PlayerTelemetry(1,population=16,population_cap=20,population_limit=200)
        self.assertIsNotNone(PopulationWarning().update('m',p,0))
        self.assertIsNone(PopulationWarning().update('m',replace(p,population_cap=None),0))
    def test_threshold_strict_one_time_and_enemy_only(self):
        r=MilitaryWarning();p=PlayerTelemetry(2,enemy=True,military_units=25)
        self.assertEqual(r.update('m',[p]),[])
        self.assertEqual(len(r.update('m',[replace(p,military_units=26)])),1)
        self.assertEqual(r.update('m',[replace(p,military_units=26)]),[])
        self.assertEqual(r.update('m',[replace(p,military_units=50)]),[])
        self.assertEqual(len(r.update('m',[replace(p,military_units=51)])),1)
        self.assertEqual(r.update('m',[replace(p,military_units=101,enemy=None)]),[])
        self.assertEqual(r.update('m',[replace(p,military_units=101,enemy=False)]),[])
    def test_threshold_jump_consolidation_and_reset(self):
        r=MilitaryWarning();p=PlayerTelemetry(2,enemy=True,military_units=110)
        self.assertEqual(len(r.update('m',[p])),1)
        r.update('m',[p],False)
        self.assertEqual(r.update('m',[p]),[])
        self.assertEqual(len(r.update('new',[p])),1)
    def plan(self,planner,rows,**kwargs):
        args=dict(enabled=True,fresh=True,foreground=True,paused=False);args.update(kwargs)
        return planner.plan('m',1,rows,**args)
    def villager(self,uid=1):
        return EvacuationObservation(uid,1,True,True,(2,),False,100,True,1,False)
    def test_evacuation_ignores_neutral_manual_attack_and_unknown(self):
        v=self.villager()
        for x in (replace(v,threatening_players=(0,)),replace(v,manual_attack=True),replace(v,manual_attack=None),replace(v,owner=2),replace(v,verified=False),replace(v,safe_route=False)):
            self.assertEqual(self.plan(EvacuationPlanner(),[x]),[])
    def test_evacuation_reserves_capacity_and_no_duplicate(self):
        p=EvacuationPlanner();rows=[self.villager(1),self.villager(2)]
        self.assertEqual(self.plan(p,rows),[(1,100)])
        self.assertEqual(self.plan(p,rows),[])
        self.assertEqual(self.plan(p,rows,foreground=False),[])
    def test_manual_order_cancels_pending_proposal(self):
        p=EvacuationPlanner();v=self.villager();self.plan(p,[v])
        self.assertEqual(self.plan(p,[replace(v,manual_attack=True)]),[])
        self.assertEqual(p.pending,{})

if __name__=='__main__':unittest.main()
