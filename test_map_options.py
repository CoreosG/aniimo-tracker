import unittest
from map_engine import MapEngine


class MapOptionsTests(unittest.TestCase):
    def test_default_map_shows_both_entrance_alternatives(self):
        model=MapEngine(39)
        options=dict(size=model.image.size,icons=dict(keys=False,eggs=False,trials=False,chests=False))
        both=model.render(**options)
        for entrance in (0,1):
            self.assertTrue(both.tobytes()!=model.render(entrance=entrance,**options).tobytes(),'Both entrance routes must remain visible')
        pixels=list(both.get_flattened_data())
        self.assertGreater(pixels.count((255,155,67)),500)
        self.assertGreater(pixels.count((101,181,255)),500)

    def test_unconfirmed_trials_are_hidden_unless_requested(self):
        model=MapEngine(40)
        options=dict(goal='none',icons=dict(keys=False,eggs=False,trials=True,chests=False))
        self.assertTrue(model.render(**options).tobytes()!=model.render(unconfirmed_trials=True,**options).tobytes())
        fixed=MapEngine(39)
        self.assertTrue(fixed.render(**options).tobytes()==fixed.render(unconfirmed_trials=True,**options).tobytes())

    def test_both_entrances_satisfy_each_goal_on_every_layout(self):
        from map_catalog import layouts_for
        layouts=set(layouts_for('Beginner')+layouts_for('Hard')+layouts_for('Chaos'))
        for layout in layouts:
            model=MapEngine(layout)
            for goal in ('keys','eggs','both'):
                for entrance in (0,1):
                    with self.subTest(layout=layout,goal=goal,entrance=entrance):
                        route=model.route(entrance,keys=2,goal=goal,eggs=1)
                        self.assertEqual(route['stops'][0],model.routes['pts'][entrance])
                        self.assertEqual(route['stops'][-1]['k'],'door')
                        for kind,count in [('key',2 if goal in ('keys','both') else 0),('nest',1 if goal in ('eggs','both') else 0)]:
                            available=sum(p['k']==kind for p in model.routes['pts'])
                            self.assertEqual(sum(p['k']==kind for p in route['stops']),min(count,available))
                        self.assertTrue(route['segments'])

    def test_egg_route_visits_nearest_nest_and_returns_to_orange(self):
        route=MapEngine(39).route(0,keys=0,goal='eggs',eggs=1)
        self.assertEqual([(p['k'],p['i']) for p in route['stops']],
                         [('door',0),('nest',4),('door',0)])
        self.assertEqual(route['distance'],112)

    def test_difficulty_pools_include_every_map_and_share_high_tiers(self):
        from map_catalog import layouts_for
        self.assertEqual(layouts_for('Beginner'),(53,54,55,56,57,58,59,60))
        self.assertEqual(layouts_for('Hard'),(41,42,45,48,49,50))
        self.assertEqual(layouts_for('Nightmare'),layouts_for('Chaos'))
        for difficulty in ('Beginner','Hard','Nightmare','Chaos'):
            for layout in layouts_for(difficulty):
                model=MapEngine(layout)
                self.assertTrue(model.route(0,1)['segments'])

    def test_each_icon_category_can_be_shown_independently_without_a_route(self):
        model=MapEngine(39)
        icons=dict(keys=False,eggs=False,trials=False,chests=False)
        plain=model.render((500,500),goal='none',icons=icons).tobytes()
        for category in icons:
            with self.subTest(category=category):
                shown=model.render((500,500),goal='none',icons={**icons,category:True})
                self.assertNotEqual(plain,shown.tobytes())

    def test_combined_route_visits_both_requested_target_counts(self):
        route=MapEngine(39).route(0,keys=2,goal='both',eggs=2)
        self.assertEqual(sum(p['k']=='key' for p in route['stops']),2)
        self.assertEqual(sum(p['k']=='nest' for p in route['stops']),2)

