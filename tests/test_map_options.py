import unittest
from map_engine import MapEngine


class MapOptionsTests(unittest.TestCase):
    def test_treasure_markers_cover_gold_rooms_without_corridor_chests(self):
        model=MapEngine(37)
        self.assertEqual(len(model.treasure_rooms),9)
        centers={(room['x'],room['y']) for room in model.treasure_rooms}
        self.assertIn((17.54,31.05),centers)
        self.assertNotIn((47.54,62.92),centers)

    def test_player_trails_are_separate_colored_layers_and_do_not_cover_planned_routes(self):
        model=MapEngine(37)
        options=dict(size=(650,650),goal='none',icons=dict(keys=False,eggs=False,trials=False,chests=False))
        trails=[dict(color='#ff82cb',segments=[[(10,10),(80,80)]])]
        plain=model.render(**options)
        with_trails=model.render(**options,trails=trails)
        self.assertNotEqual(plain.tobytes(),with_trails.tobytes())
        self.assertGreater(list(with_trails.get_flattened_data()).count((255,130,203)),100)
        planned={**options,'goal':'keys'}
        before=list(model.render(**planned).get_flattened_data())
        after=list(model.render(**planned,trails=trails).get_flattened_data())
        for color in ((255,177,47),(114,107,255)):
            self.assertEqual(before.count(color),after.count(color),'Planned routes stay above the thin trails')

    def test_exit_preference_applies_to_both_entrances(self):
        model=MapEngine(39)
        for start in (0,1):
            for exit,name in ((0,'orange'),(1,'blue')):
                self.assertEqual(model.route(start,goal='eggs',exit=name)['stops'][-1],model.routes['pts'][exit])

    def test_rich_rooms_and_trials_are_distinct_route_goals(self):
        model=MapEngine(32)
        for goal,kind in (('rich','room'),('trials','challenge')):
            for entrance in (0,1):
                route=model.route(entrance,goal=goal,rooms=2)
                count=min(2,sum(p['k']==kind for p in model.routes['pts']))
                self.assertEqual(sum(p['k']==kind for p in route['stops']),count)
                self.assertTrue(all(p['k'] in ('door',kind) for p in route['stops']))

    def test_monsters_and_legend_can_be_toggled(self):
        model=MapEngine(32)
        options=dict(goal='none',icons=dict(keys=False,eggs=False,trials=False,chests=False,monsters=False))
        plain=model.render(**options).tobytes()
        self.assertTrue(plain!=model.render(**{**options,'icons':dict(options['icons'],monsters=True)}).tobytes())
        self.assertTrue(plain!=model.render(**options,legend=True).tobytes())

    def test_player_marker_is_a_circle_without_an_implied_heading(self):
        model=MapEngine(39)
        image=model.render((500,500),player=[50,50],live=True,goal='none',
                           icons=dict(keys=False,eggs=False,trials=False,chests=False))
        self.assertEqual(image.getpixel((250,260)),(255,255,255))
        self.assertEqual(image.getpixel((250,240)),(255,255,255))

    def test_default_map_shows_both_entrance_alternatives(self):
        model=MapEngine(39)
        options=dict(size=model.image.size,icons=dict(keys=False,eggs=False,trials=False,chests=False))
        both=model.render(**options)
        for entrance in (0,1):
            self.assertTrue(both.tobytes()!=model.render(entrance=entrance,**options).tobytes(),'Both entrance routes must remain visible')
        pixels=list(both.get_flattened_data())
        self.assertGreater(pixels.count((255,177,47)),500)
        self.assertGreater(pixels.count((114,107,255)),500)

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

