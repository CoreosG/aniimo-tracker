import tempfile
import unittest
from unittest.mock import patch
from app import App


class IdleOverlayTests(unittest.TestCase):
    def test_outside_dungeon_has_one_navigation_status_and_keeps_run_actions(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as directory, patch('sanctum_panel.game_is_foreground', return_value=True):
            app = App(directory, hotkeys=False)
            try:
                app.ledger.configure(capture_target='monitor')
                app.begin_run(without_balance=True)
                app.busy_capture=True  # No desktop capture needed for these observations.
                panel=app.sanctum
                for _ in range(2):
                    panel.messages.put((panel.generation,Image.new('RGB',(2,2)),
                        {'minimap':True,'automatic':{'kind':'outside'}},None))
                panel.tick()
                shown=' '.join(panel.overlay.canvas.itemcget(i,'text') for i in panel.overlay.canvas.find_all() if panel.overlay.canvas.type(i)=='text')
                self.assertIn('Outside dungeon',shown)
                self.assertIn('Run active',shown)
                self.assertNotIn('waiting for',shown.lower())
                self.assertIn('Loot',shown)
                self.assertLess(panel.overlay.window.winfo_height(),70)
                app.set_language('pt-BR');panel.show_overlay()
                shown=' '.join(panel.overlay.canvas.itemcget(i,'text') for i in panel.overlay.canvas.find_all() if panel.overlay.canvas.type(i)=='text')
                self.assertIn('Fora da masmorra',shown)
                self.assertIn('Partida ativa',shown)
                self.assertNotIn('aguardando',shown.lower())
            finally:
                app.set_language('en')
                app.close()

    def test_optional_idle_bar_stays_between_runs_and_respects_hide_and_focus(self):
        with tempfile.TemporaryDirectory() as directory, patch('sanctum_panel.game_is_foreground', return_value=True):
            app = App(directory, hotkeys=False)
            app.ledger.configure(capture_target='monitor')
            try:
                panel = app.sanctum
                panel.tick(); app.update_idletasks()
                self.assertFalse(panel.overlay.visible)
                panel.always_status.set(True); panel.save_preferences(); panel.tick()
                self.assertTrue(panel.overlay.visible)
                self.assertLess(panel.overlay.window.winfo_height(), 70)
                self.assertFalse(panel.overlay.movable)
                shown = ' '.join(panel.overlay.canvas.itemcget(i, 'text') for i in panel.overlay.canvas.find_all() if panel.overlay.canvas.type(i) == 'text')
                self.assertIn('Ready', shown)
                self.assertIn('Ctrl+Shift+F8', shown)
                app.begin_run(manual=True)
                self.assertIsNone(app.ledger.active_start()['balance'])
                app.fields['points'].set('170')
                self.assertTrue(app.quick_save_run())
                panel.tick()
                self.assertTrue(panel.overlay.visible)
                self.assertLess(panel.overlay.window.winfo_height(), 70)
                panel.overlay_enabled.set(False); panel.toggle_overlay(); panel.tick()
                self.assertFalse(panel.overlay.visible)
                panel.overlay_enabled.set(True); panel.toggle_overlay()
                with patch('sanctum_panel.game_is_foreground', return_value=False):
                    panel.tick()
                    self.assertFalse(panel.overlay.visible)
            finally:
                app.close()
            reopened = App(directory, hotkeys=False)
            try:
                self.assertTrue(reopened.sanctum.always_status.get())
            finally:
                reopened.close()
