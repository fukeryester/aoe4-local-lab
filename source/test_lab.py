import unittest,math
from reader import Camera,project,bounded,Reader
from layout import arrange

class ProjectionTests(unittest.TestCase):
    def test_center_and_right(self):
        cam=Camera((0,0,0),(0,0,1),90)
        self.assertEqual(project((0,0,10),cam,1920,1080),(960,540,10))
        x,y,z=project((1,0,10),cam,1920,1080)
        self.assertAlmostEqual(x,1014);self.assertAlmostEqual(y,540)
    def test_behind_camera_and_outside_view_are_not_drawn(self):
        cam=Camera((0,0,0),(0,0,1),90)
        self.assertIsNone(project((0,0,-1),cam,1920,1080))
        self.assertIsNone(project((100,0,1),cam,1920,1080))
    def test_actual_paused_match_anchor(self):
        cam=Camera((112.0519867,54.5094566,-172.9893951),(146.0519714,6.4262161,-138.9893951),41.1000023)
        x,y,_=project((128,6.95109415,-128),cam,2560,1440)
        self.assertAlmostEqual(x,664.7,delta=.1);self.assertAlmostEqual(y,814.7,delta=.1)
    def test_degenerate_camera_rejected(self):
        with self.assertRaises(ValueError):project((0,1,1),Camera((0,0,0),(0,0,0),45),800,600)

class GuardTests(unittest.TestCase):
    def test_invalid_container_count(self):
        for n in (-1,100001):
            with self.assertRaises(ValueError):bounded(n,100000,'entity count')
    def test_unreadable_process_fails_without_sample_data(self):
        with self.assertRaises(OSError):Reader(0)

class LayoutTests(unittest.TestCase):
    def test_collocated_names_keep_distinct_positions_and_anchors(self):
        labels=[(i,400,400,'村民','#188cff') for i in range(8)]
        placed=arrange(labels,14,1000,800)
        self.assertEqual(len({(v[3],v[4]) for v in placed}),8)
        self.assertTrue(all((v[1],v[2])==(400,400) for v in placed))
    def test_names_stay_in_view(self):
        placed=arrange([(1,0,1,'villager','#fff'),(2,999,799,'绵羊','#fff')],14,1000,800)
        self.assertTrue(all(0<v[3]<1000 and 0<v[4]<800 for v in placed))

if __name__=='__main__':unittest.main(verbosity=2)
