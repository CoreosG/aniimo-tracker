import tempfile
import time
import unittest
from unittest.mock import patch

from app import App
from map_engine import MapEngine
from tests.test_minimap_recognition import hud
from tests.test_portal_occlusion import entry_map,outdoor_map
from PIL import Image
from party_protocol import evidence_score


class AutomaticNavigationTests(unittest.TestCase):
    def observe(self,app,frame,count=3):
        with patch('sanctum_panel.capture_image',return_value=frame):
            for _ in range(count):
                app.sanctum.scan()
                deadline=time.monotonic()+4
                while app.sanctum.busy and time.monotonic()<deadline:app.update();time.sleep(.01)
                time.sleep(.4)

    def test_outdoor_full_map_hides_previous_navigation_and_next_dungeon_recovers(self):
        with tempfile.TemporaryDirectory() as directory,patch('sanctum_panel.game_is_foreground',return_value=False),patch('sanctum_panel.capture_bounds',return_value=(0,0,1920,1080)):
            app=App(directory,hotkeys=False)
            try:
                panel=app.sanctum;panel.watch_action()
                self.observe(app,entry_map(covered=False),count=1)
                self.assertTrue(panel.session.map_confirmed)
                self.observe(app,outdoor_map(),count=1)
                self.assertTrue(panel.outdoors)
                self.assertIsNone(panel.player)
                self.assertEqual(panel.map_feedback,'Outside dungeon')
                self.observe(app,entry_map(covered=False,reverse=True),count=1)
                self.assertFalse(panel.outdoors)
                self.assertEqual(panel.engine.layout,40)
            finally:app.close()

    def test_M_remains_available_with_automatic_matching_disabled(self):
        with tempfile.TemporaryDirectory() as directory,patch('sanctum_panel.game_is_foreground',return_value=False),patch('sanctum_panel.capture_bounds',return_value=(0,0,1280,720)):
            app=App(directory,hotkeys=False)
            try:
                app.ledger.configure(capture_target='monitor')
                panel=app.sanctum;panel.watch_action();panel.automatic_minimap.set(False);panel.save_preferences()
                self.observe(app,hud(MapEngine(37).reference,(350,600)))
                self.assertFalse(panel.session.map_confirmed)
                self.observe(app,entry_map(covered=False),count=1)
                self.assertTrue(panel.session.map_confirmed)
                self.assertEqual(panel.engine.layout,32)
            finally:app.close()

    def test_minimap_does_not_replace_a_full_map_but_outdoors_hides_navigation(self):
        with tempfile.TemporaryDirectory() as directory,patch('sanctum_panel.game_is_foreground',return_value=False),patch('sanctum_panel.capture_bounds',return_value=(0,0,1280,720)):
            app=App(directory,hotkeys=False)
            try:
                app.ledger.configure(capture_target='monitor')
                panel=app.sanctum;panel.watch_action()
                self.observe(app,entry_map(covered=False),count=1)
                self.assertEqual(panel.engine.layout,32)
                self.observe(app,hud(MapEngine(37).reference,(350,600)))
                self.assertEqual(panel.engine.layout,32,'M remains authoritative in this dungeon')
                self.observe(app,hud(Image.new('RGB',(1024,1024),(65,125,70))))
                self.assertTrue(panel.outdoors)
                self.assertIsNone(panel.player)
                self.assertIsNone(app.ledger.active_start())
                self.observe(app,hud(MapEngine(37).reference,(350,600)))
                self.assertFalse(panel.outdoors)
                self.assertEqual(panel.engine.layout,37,'Fresh evidence may identify the next dungeon after an outdoor transition')
            finally:app.close()

    def test_map_only_identifies_corridors_without_M_or_creating_a_ledger_run(self):
        frame=hud(MapEngine(37).reference,(350,600))
        with tempfile.TemporaryDirectory() as directory,patch('sanctum_panel.game_is_foreground',return_value=False),patch('sanctum_panel.capture_image',return_value=frame),patch('sanctum_panel.capture_bounds',return_value=(0,0,1280,720)):
            app=App(directory,hotkeys=False)
            try:
                app.ledger.configure(capture_target='monitor')
                panel=app.sanctum;panel.watch_action()
                for _ in range(3):
                    panel.scan()
                    deadline=time.monotonic()+4
                    while panel.busy and time.monotonic()<deadline:app.update();time.sleep(.01)
                    time.sleep(.4)
                self.assertTrue(panel.session.map_confirmed,panel.status.get())
                self.assertEqual(panel.engine.layout,37)
                self.assertEqual(evidence_score(panel.last_reading),.8,'A later party connection must be able to share local recognition')
                self.assertIsNotNone(panel.player)
                self.assertIsNone(app.ledger.active_start())
                self.assertTrue(panel.session.standalone)
            finally:app.close()
