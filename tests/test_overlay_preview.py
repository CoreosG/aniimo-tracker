import tempfile
import unittest
from unittest.mock import patch
from app import App


class OverlayPreviewTests(unittest.TestCase):
    def test_overlay_status_stays_compact_with_long_shortcuts_and_notices(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as directory,patch('sanctum_panel.game_is_foreground',return_value=False):
            app=App(directory,hotkeys=False)
            app.ledger.configure(capture_target='monitor')
            try:
                overlay=app.sanctum.overlay
                overlay.show(Image.new('RGB',(350,1),'#000001'),(20,20,0,0),label='Chaos 39 · Run active · previous run unfinished · waiting for map · '*3,
                             details='Run active\nLoot 1.25M · Pts 400 · Ctrl+Shift+Alt+F12 save')
                app.update_idletasks()
                self.assertLessEqual(overlay.window.winfo_height(),75)
            finally:app.close()

    def test_large_overlay_is_kept_inside_a_small_display(self):
        with tempfile.TemporaryDirectory() as directory,patch('sanctum_panel.game_is_foreground',return_value=False):
            app=App(directory,hotkeys=False)
            app.ledger.configure(capture_target='monitor')
            try:
                app.sanctum.overlay_size.set(950)
                app.sanctum.config['overlay_position']=[600,450]
                with patch('sanctum_panel.monitors',return_value=[dict(bbox=(0,0,640,480),primary=True)]):
                    app.sanctum.show_overlay(preview=True)
                    app.update_idletasks()
                window=app.sanctum.overlay.window
                self.assertLessEqual(window.winfo_x()+window.winfo_width(),640)
                self.assertLessEqual(window.winfo_y()+window.winfo_height(),480)
            finally:app.close()

    def test_map_only_start_shows_status_in_game_before_map_pack_download(self):
        with tempfile.TemporaryDirectory() as directory,patch('map_setup_panel.maps_ready',return_value=False),patch('sanctum_panel.game_is_foreground',return_value=False):
            app=App(directory,hotkeys=False)
            app.ledger.configure(capture_target='monitor')
            try:
                baseline=app.ledger.summary()
                app.sanctum.watch_action()
                with patch('sanctum_panel.game_is_foreground',return_value=True):
                    app.sanctum.tick();app.update_idletasks()
                    self.assertTrue(app.sanctum.overlay.visible)
                    canvas=app.sanctum.overlay.canvas
                    texts=' '.join(canvas.itemcget(item,'text') for item in canvas.find_all() if canvas.type(item)=='text')
                    self.assertIn('Map pack required',texts)
                    self.assertIsNone(app.ledger.active_start())
                    self.assertEqual(app.ledger.summary(),baseline)
                    app.sanctum.watch_action();app.sanctum.tick()
                    self.assertFalse(app.sanctum.overlay.visible)
            finally:app.close()

    def test_map_only_overlay_keeps_map_status_without_ledger_lines(self):
        with tempfile.TemporaryDirectory() as directory,patch('sanctum_panel.game_is_foreground',return_value=False):
            app=App(directory,hotkeys=False)
            app.ledger.configure(capture_target='monitor')
            try:
                app.sanctum.watch_action()
                app.busy_capture=True
                with patch('sanctum_panel.game_is_foreground',return_value=True):
                    app.sanctum.tick();app.update_idletasks()
                    self.assertTrue(app.sanctum.overlay.visible)
                canvas=app.sanctum.overlay.canvas
                texts=' '.join(canvas.itemcget(item,'text') for item in canvas.find_all() if canvas.type(item)=='text')
                self.assertIn('Waiting for map',texts)
                self.assertNotIn('Loot',texts)
                self.assertNotIn('run',texts)
            finally:app.close()

    def test_adjustments_preview_without_confirming_map_or_changing_run(self):
        with tempfile.TemporaryDirectory() as directory,patch('sanctum_panel.game_is_foreground',return_value=False),patch('sanctum_panel.app_is_foreground',return_value=True):
            app=App(directory,hotkeys=False)
            app.ledger.configure(capture_target='monitor')
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
