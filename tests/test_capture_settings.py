import tempfile
import unittest
from unittest.mock import patch
from app import App


class CaptureSettingsTests(unittest.TestCase):
    def test_window_default_and_explicit_monitor_choice_persist_without_changing_stats(self):
        with tempfile.TemporaryDirectory() as directory,patch('sanctum_panel.game_is_foreground',return_value=False):
            app=App(directory,hotkeys=False)
            try:
                self.assertEqual(app.ledger.settings()['capture_target'],'auto')
                baseline=app.ledger.summary()
                app.ledger.configure(regions=dict(points=[.1,.2,.3,.4]))
                app.sanctum.config['minimap_region']=[.1,.2,.3,.4]
                app.capture_target_choice.current(1)
                app.select_capture_target()
                self.assertEqual(app.ledger.settings()['capture_target'],'monitor')
                self.assertEqual(app.ledger.settings()['regions'],{})
                self.assertNotIn('minimap_region',app.sanctum.config)
                self.assertEqual(app.ledger.summary(),baseline)
            finally:app.close()
            reopened=App(directory,hotkeys=False)
            try:
                self.assertEqual(reopened.capture_target_choice.current(),1)
                self.assertEqual(reopened.ledger.settings()['capture_target'],'monitor')
            finally:reopened.close()
