import tempfile
import unittest
from unittest.mock import patch
from app import App


class OverlayPreviewTests(unittest.TestCase):
    def test_map_only_overlay_keeps_map_status_without_ledger_lines(self):
        with tempfile.TemporaryDirectory() as directory,patch('sanctum_panel.game_is_foreground',return_value=False):
            app=App(directory,hotkeys=False)
            try:
                app.sanctum.watch_action();app.sanctum.show_overlay()
                canvas=app.sanctum.overlay.canvas
                texts=' '.join(canvas.itemcget(item,'text') for item in canvas.find_all() if canvas.type(item)=='text')
                self.assertIn('Waiting for map',texts)
                self.assertNotIn('Loot',texts)
                self.assertNotIn('run',texts)
            finally:app.close()

    def test_adjustments_preview_without_confirming_map_or_changing_run(self):
        with tempfile.TemporaryDirectory() as directory,patch('sanctum_panel.game_is_foreground',return_value=False),patch('sanctum_panel.app_is_foreground',return_value=True):
            app=App(directory,hotkeys=False)
            try:
                app.tabs.select(1);app.update();panel=app.sanctum
                baseline=app.ledger.summary()
                panel.opacity.set(45);panel.overlay_size.set(440);panel.adjust_overlay();app.update()
                self.assertTrue(panel.overlay.visible)
                self.assertAlmostEqual(panel.overlay.window.attributes('-alpha'),.45,places=2)
                self.assertEqual(panel.overlay.window.winfo_width(),440)
                self.assertIsNone(panel.engine)
                self.assertFalse(panel.session.map_confirmed)
                panel.zoom.set(2);panel.adjust_overlay();app.update()
                self.assertTrue(panel.overlay.visible)
                with patch('sanctum_panel.app_is_foreground',return_value=False):
                    panel.tick();self.assertFalse(panel.overlay.visible)
                panel.tick();self.assertTrue(panel.overlay.visible)
                app.tabs.select(2);panel.tick();self.assertFalse(panel.overlay.visible)
                self.assertFalse(panel.preview_overlay.get())
                self.assertEqual(app.ledger.summary(),baseline)
            finally:app.close()
