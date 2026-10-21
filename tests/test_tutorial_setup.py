import tempfile
import threading
import unittest
from unittest.mock import patch

from app import App


class TutorialSetupTests(unittest.TestCase):
    def test_setup_actions_open_stats_and_install_maps_without_starting_a_run(self):
        with tempfile.TemporaryDirectory() as directory,patch('sanctum_panel.game_is_foreground',return_value=False),patch('map_setup_panel.maps_ready',return_value=False):
            app=App(directory,hotkeys=False)
            try:
                tutorial=app.tutorial;tutorial.open();app.update_idletasks()
                baseline=app.ledger.summary()
                self.assertIn('Not installed',tutorial.setup_status.get())
                tutorial.stats_button.invoke()
                self.assertTrue(app.stats_editor.winfo_exists())
                self.assertIsNone(app.ledger.active_start())
                app.stats_editor.destroy()
                # Network download is the external boundary; the real setup
                # worker receives a successful installation without fetching.
                installed=threading.Event()
                with patch('setup_maps.install',side_effect=lambda *a,**k:installed.set()):
                    tutorial.download_button.invoke()
                    self.assertEqual(app.tabs.select(),str(app.sanctum_tab))
                    self.assertTrue(app.sanctum.map_setup.busy)
                    self.assertTrue(installed.wait(2))
                self.assertEqual(app.ledger.summary(),baseline)
            finally:app.close()

    def test_first_use_annotations_and_reopen_keep_custom_shortcuts_and_saved_stats(self):
        with tempfile.TemporaryDirectory() as directory,patch('sanctum_panel.game_is_foreground',return_value=False):
            app=App(directory,hotkeys=False)
            try:
                app.shortcuts.update(capture='F6',save='F7',overlay='F10',map='Tab')
                tutorial=app.tutorial;tutorial.first_use()
                self.assertTrue(tutorial.window.winfo_exists())
                for _ in range(3):tutorial.next.invoke()
                app.update_idletasks()
                labels=[tutorial.canvas.itemcget(item,'text') for item in tutorial.canvas.find_withtag('annotation') if tutorial.canvas.type(item)=='text']
                self.assertEqual(labels,['TOTAL','RUN AWARD','EMPEROR EGGS'])
                self.assertIn('F6',tutorial.copy.cget('text'))
                self.assertIn('F7',tutorial.copy.cget('text'))
                tutorial.close();tutorial.first_use()
                self.assertIsNone(tutorial.window)
                tutorial.open()
                self.assertEqual(tutorial.index,0)
                self.assertTrue(tutorial.download_button.winfo_exists())
                tutorial.close()
            finally:app.close()
