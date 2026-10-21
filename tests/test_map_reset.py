import tempfile
import time
import unittest
from unittest.mock import patch

from app import App


class MapResetTests(unittest.TestCase):
    def test_map_only_waiting_overlay_survives_a_disconnected_saved_display(self):
        with tempfile.TemporaryDirectory() as directory,patch('sanctum_panel.game_is_foreground',return_value=False), \
                patch('sanctum_panel.capture_bounds',return_value=(100,100,1380,820)), \
                patch('sanctum_panel.monitors',return_value=[dict(primary=True,bbox=(0,0,1920,1080))]):
            app=App(directory,hotkeys=False)
            try:
                app.ledger.configure(monitor=99,capture_target='auto')
                app.sanctum.watch_action()
                app.busy_capture=True
                with patch('sanctum_panel.game_is_foreground',return_value=True):
                    app.sanctum.tick()
                self.assertTrue(app.sanctum.overlay.visible)
                self.assertIsNone(app.ledger.active_start())
            finally:app.close()

    def test_auto_layout_selection_rearms_detection_after_a_live_position(self):
        with tempfile.TemporaryDirectory() as directory, patch('sanctum_panel.game_is_foreground', return_value=False):
            app = App(directory, hotkeys=False)
            try:
                panel = app.sanctum
                panel.watch_action()
                panel.accept_layout(39, dict(candidates=[39], orange=[100, 500], blue=[100, 100]))
                panel.player = [50, 50]
                panel.position_time = time.monotonic() - 3
                self.assertTrue(panel.session.map_confirmed)
                before = app.ledger.summary()

                panel.layout.set('Auto / waiting')
                panel.select_layout()
                panel.tick()

                self.assertFalse(panel.session.map_confirmed)
                self.assertIsNone(panel.engine)
                self.assertIsNone(panel.player)
                self.assertTrue(panel.session.watching)
                self.assertEqual(app.ledger.summary(), before)
            finally:
                app.close()
