import unittest
from player_trails import PlayerTrails


class PlayerTrailTests(unittest.TestCase):
    def test_paths_break_at_exits_gaps_and_jumps_and_reset_for_new_navigation(self):
        trails=PlayerTrails(limit=6)
        trails.reset(('party',1,37))
        for point,now in [([10,10],0),([11,10],1),(None,2),([70,70],3),([71,70],4)]:
            trails.observe('one','#3df5ff',point,now)
        self.assertEqual(trails.paths()[0]['segments'],[[(10,10),(11,10)],[(70,70),(71,70)]])
        trails.observe('one','#3df5ff',[5,5],5)
        self.assertEqual(trails.paths()[0]['segments'][-1],[(5,5)])
        trails.reset(('party',2,37))
        self.assertEqual(trails.paths(),[])

    def test_memory_is_bounded_and_stationary_samples_do_not_fill_it(self):
        trails=PlayerTrails(limit=6)
        for i in range(5000):trails.observe('one','#3df5ff',[10+i%5,10],i*.7)
        self.assertLessEqual(sum(map(len,trails.paths()[0]['segments'])),6)
        before=trails.paths()
        for i in range(5000):trails.observe('one','#3df5ff',[14,10],3500+i*.7)
        self.assertEqual(trails.paths(),before)
        for identity in ('two','three','four'):trails.observe(identity,'#ff82cb',[10,10],8000)
        self.assertLessEqual(len(trails.paths()),3)
