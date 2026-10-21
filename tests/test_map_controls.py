import tempfile
import unittest
import json
from pathlib import Path
from unittest.mock import patch
from app import App


class MapControlsTests(unittest.TestCase):
    def test_persistent_bar_prompts_to_finish_a_pending_result_before_starting(self):
        with tempfile.TemporaryDirectory() as directory,patch('sanctum_panel.game_is_foreground',return_value=True):
            app=App(directory,hotkeys=False)
            try:
                app.ledger.configure(capture_target='monitor')
                panel=app.sanctum;panel.always_status.set(True);panel.save_preferences()
                app.fields['money'].set('500000');panel.tick()
                shown=' '.join(panel.overlay.canvas.itemcget(i,'text') for i in panel.overlay.canvas.find_all() if panel.overlay.canvas.type(i)=='text')
                self.assertNotIn('start run',shown)
                app.fields['points'].set('170');panel.tick()
                shown=' '.join(panel.overlay.canvas.itemcget(i,'text') for i in panel.overlay.canvas.find_all() if panel.overlay.canvas.type(i)=='text')
                self.assertIn('Ctrl+Shift+F9 save',shown)
            finally:app.close()

    def test_retired_start_binding_preserves_custom_capture_and_overlay(self):
        with tempfile.TemporaryDirectory() as directory,patch('sanctum_panel.game_is_foreground',return_value=False):
            Path(directory,'shortcuts.json').write_text(json.dumps(dict(start='Ctrl+Shift+F7',capture='F6',overlay='F2')))
            app=App(directory,hotkeys=False)
            try:
                self.assertEqual(app.shortcuts['capture'],'F6')
                self.assertEqual(app.shortcuts['overlay'],'F2')
                self.assertNotIn('start',app.shortcuts)
            finally:app.close()

    def test_idle_bar_shows_the_unified_start_capture_shortcut(self):
        with tempfile.TemporaryDirectory() as directory,patch('sanctum_panel.game_is_foreground',return_value=True):
            app=App(directory,hotkeys=False)
            try:
                app.ledger.configure(capture_target='monitor')
                panel=app.sanctum;panel.always_status.set(True);panel.save_preferences();panel.tick()
                shown=' '.join(panel.overlay.canvas.itemcget(i,'text') for i in panel.overlay.canvas.find_all() if panel.overlay.canvas.type(i)=='text')
                self.assertIn('Ctrl+Shift+F8 start run',shown)
                self.assertNotIn('F7',shown)
            finally:app.close()

    def test_visible_section_buttons_and_persistent_bar_toggle_in_both_languages(self):
        with tempfile.TemporaryDirectory() as directory,patch('sanctum_panel.game_is_foreground',return_value=False):
            app=App(directory,hotkeys=False)
            try:
                app.tabs.select(app.sanctum_tab);app.update()
                panel=app.sanctum
                for language in ('en','pt-BR'):
                    app.set_language(language)
                    for section in ('Icons','Overlay','Tools','Route'):
                        panel.section_buttons[section].invoke();app.update()
                        self.assertTrue(panel.map_sections[section].winfo_ismapped())
                        self.assertEqual([name for name,frame in panel.map_sections.items() if frame.winfo_ismapped()],[section])
                    self.assertTrue(panel.persistent_check.winfo_ismapped())
                panel.persistent_check.invoke()
                self.assertTrue(panel.always_status.get())
                self.assertNotEqual(panel.persistent_check.master,panel.advanced)
            finally:app.close()
