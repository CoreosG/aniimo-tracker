import unittest
import io
import json
import tempfile
import time
from pathlib import Path
from unittest.mock import patch
from app import App
from update_checker import release_info


class UpdateTests(unittest.TestCase):
    def test_update_waits_for_capture_then_preserves_draft_before_deferred_restart(self):
        from tests.test_update_install import Response
        with tempfile.TemporaryDirectory() as directory,patch('sanctum_panel.game_is_foreground',return_value=False):
            app=App(directory,hotkeys=False)
            try:
                target=Path(directory)/'AniimoTracker.exe';target.write_bytes(b'old executable')
                app.updates.info=dict(version='9.9.9',available=True,download_url='https://github.com/CoreosG/aniimo-tracker/releases/download/v9.9.9/AniimoTracker.exe',sha256='d20ddd75a42c4db549cd1fa807dd9fbaaa30d2c02391587a2ea6d27d2950795d',size=6)
                app.fields['points'].set('170');app.pending_ocr.add('points')
                with patch('sys.frozen',True,create=True),patch('sys.executable',str(target)),patch('urllib.request.OpenerDirector.open',return_value=Response(b'MZtest')),patch('update_install.subprocess.Popen') as launched:
                    app.updates.install_update()
                    deadline=time.time()+3
                    while not app.updates.pending_install and time.time()<deadline:app.updates.tick();time.sleep(.01)
                    self.assertIsNotNone(app.updates.pending_install)
                    launched.assert_not_called()
                    app.pending_ocr.clear()
                    app.tick()
                    self.assertTrue(app.updates.restart_pending)
                    self.assertEqual(launched.call_args.args[0][1],'--apply-update')
                    app.update_idletasks()
                    self.assertTrue(app.winfo_exists())
                    app.update()
                app=None
                reopened=App(directory,hotkeys=False)
                try:self.assertEqual(reopened.fields['points'].get(),'170')
                finally:reopened.close()
            finally:
                if app:app.close()

    def test_startup_check_ignores_old_daily_cache_and_repeats_each_30_minutes(self):
        feed=dict(version='9.9.9',download_url='https://github.com/CoreosG/aniimo-tracker/releases/download/v9.9.9/AniimoTracker.exe',sha256='a'*64,size=100)
        with tempfile.TemporaryDirectory() as directory,patch('sanctum_panel.game_is_foreground',return_value=False),patch('update_checker.time.monotonic',return_value=100) as clock:
            Path(directory,'update-state.json').write_text(json.dumps(dict(checked=time.time(),enabled=True)))
            app=App(directory,hotkeys=False)
            try:
                panel=app.updates;panel.automatic=True
                with patch('update_checker.urlopen',side_effect=lambda *a,**k:io.BytesIO(json.dumps(feed).encode())) as network:
                    clock.return_value=103;panel.tick()
                    deadline=time.time()+2
                    while panel.busy and time.time()<deadline:panel.tick();time.sleep(.01)
                    self.assertEqual(network.call_count,1)
                    self.assertTrue(app.update_notice_frame.winfo_manager())
                    self.assertIn('9.9.9',app.update_notice.get())
                    clock.return_value=1902;panel.tick();self.assertEqual(network.call_count,1)
                    clock.return_value=1903;panel.tick()
                    deadline=time.time()+2
                    while panel.busy and time.time()<deadline:panel.tick();time.sleep(.01)
                    self.assertEqual(network.call_count,2)
                    panel.enabled.set(False);panel.save()
                    clock.return_value=3703;panel.tick();self.assertEqual(network.call_count,2)
            finally:app.close()

    def test_new_release_is_available_but_equal_or_older_release_is_not(self):
        feed=dict(version='0.3.0',download_url='https://github.com/CoreosG/aniimo-tracker/releases/download/v0.3.0/AniimoTracker.exe')
        self.assertTrue(release_info(feed,'0.2.0')['available'])
        self.assertFalse(release_info(feed,'0.3.0')['available'])
        self.assertFalse(release_info(feed,'1.0.0')['available'])

    def test_update_links_must_match_the_release_in_this_repository(self):
        for address in ('http://example.com/app.exe','https://example.com/app.exe',
                        'https://github.com/other/project/releases/download/v0.3.0/AniimoTracker.exe'):
            with self.subTest(address=address),self.assertRaises(ValueError):
                release_info(dict(version='0.3.0',download_url=address),'0.2.0')
