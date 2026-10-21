import tempfile
import unittest
import time
import json
from pathlib import Path
from types import SimpleNamespace
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

    def test_new_start_default_never_replaces_an_existing_custom_shortcut(self):
        with tempfile.TemporaryDirectory() as directory,patch('sanctum_panel.game_is_foreground',return_value=False):
            Path(directory,'shortcuts.json').write_text(json.dumps(dict(capture='Ctrl+Shift+F7',overlay='F2')))
            app=App(directory,hotkeys=False)
            try:
                self.assertEqual(app.shortcuts['capture'],'Ctrl+Shift+F7')
                self.assertEqual(app.shortcuts['overlay'],'F2')
                self.assertEqual(app.shortcuts['start'],'')
            finally:app.close()

    def test_start_hint_shortcut_starts_a_balanceless_run_from_map_only(self):
        with tempfile.TemporaryDirectory() as directory,patch('sanctum_panel.game_is_foreground',return_value=True):
            app=App(directory,hotkeys=False)
            try:
                app.ledger.configure(capture_target='monitor')
                panel=app.sanctum;panel.always_status.set(True);panel.save_preferences();panel.tick()
                shown=' '.join(panel.overlay.canvas.itemcget(i,'text') for i in panel.overlay.canvas.find_all() if panel.overlay.canvas.type(i)=='text')
                self.assertIn('Ctrl+Shift+F7 start run',shown)
                panel.watch_action()
                actions=[4]
                def poll():
                    result=actions[:];actions.clear();return result
                app.hk=SimpleNamespace(poll=poll,poll_map_key_events=lambda:[],close=lambda:None)
                deadline=time.monotonic()+2
                while not app.ledger.active_start() and time.monotonic()<deadline:app.update();time.sleep(.01)
                self.assertIsNotNone(app.ledger.active_start())
                self.assertIsNone(app.ledger.active_start()['balance'])
                self.assertFalse(panel.session.standalone)
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
