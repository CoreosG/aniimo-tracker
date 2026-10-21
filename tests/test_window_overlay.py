import tempfile
import unittest
import time
from types import SimpleNamespace
from unittest.mock import patch, Mock
from app import App


class WindowOverlayTests(unittest.TestCase):
    def test_selected_window_ignores_other_aniimo_window_focus_and_map_keys(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch('sanctum_panel.game_is_foreground',return_value=False):
                app=App(directory,hotkeys=False)
            try:
                first=dict(target=dict(hwnd=101,pid=201,process=r'c:\games\aniimo.exe',created=500),
                           name='Aniimo A',minimized=False,bbox=(100,100,1380,820))
                second=dict(target=dict(hwnd=102,pid=202,process=r'c:\games\aniimo.exe',created=501),
                            name='Aniimo B',minimized=False,bbox=(200,200,1480,920))
                native=SimpleNamespace(user=SimpleNamespace(GetForegroundWindow=Mock(return_value=101)),
                                       read=Mock(side_effect=lambda hwnd:{101:first,102:second}.get(hwnd)),
                                       list=Mock(return_value=[first,second]))
                app.ledger.configure(capture_target=first['target'])
                panel=app.sanctum;app.busy_capture=True;panel.watch_action()
                with patch('capture_target.NativeWindows',return_value=native), \
                        patch('sanctum_panel.capture_bounds',return_value=first['bbox']), \
                        patch('sanctum_panel.binding_down',return_value=False):
                    panel.tick();self.assertTrue(panel.overlay.visible)
                    native.user.GetForegroundWindow.return_value=102
                    app.hk=SimpleNamespace(poll_map_key_events=Mock(side_effect=[[(0x4D,time.monotonic())],[]]))
                    panel.poll_map_keys()
                    self.assertFalse(panel.map_open,'Another Aniimo window must not toggle the selected map session')
                    panel.tick();self.assertFalse(panel.overlay.visible)
                    native.user.GetForegroundWindow.return_value=101
                    app.hk=SimpleNamespace(poll_map_key_events=Mock(return_value=[(0x4D,time.monotonic()+.1)]))
                    panel.poll_map_keys()
                    self.assertTrue(panel.map_open)
            finally:
                app.hk=None;app.close()

    def test_overlay_moves_with_the_game_and_client_minimap_region_survives_resize(self):
        with tempfile.TemporaryDirectory() as directory, patch('sanctum_panel.game_is_foreground', return_value=False):
            app=App(directory,hotkeys=False)
            try:
                app.ledger.configure(capture_target='auto')
                panel=app.sanctum
                panel.overlay_size.set(350)
                panel.config['overlay_position']=[400,200]
                panel.config['minimap_region']=[.01,.02,.15,.2]
                with patch('sanctum_panel.capture_bounds',return_value=(100,100,1380,820)):
                    panel.show_overlay(header_only=True)
                self.assertNotIn('minimap_region',panel.config,'Old monitor calibration must not be applied to a window crop')
                self.assertEqual(panel.config['capture_space'],'client')
                self.assertEqual(panel.overlay.position,(400,200))
                panel.config['minimap_region']=[.02,.03,.2,.3]
                with patch('sanctum_panel.capture_bounds',return_value=(300,180,1580,900)):
                    panel.show_overlay(header_only=True)
                self.assertEqual(panel.overlay.position,(600,280))
                with patch('sanctum_panel.capture_bounds',return_value=(300,180,1900,1080)):
                    panel.show_overlay(header_only=True)
                self.assertEqual(panel.config['minimap_region'],[.02,.03,.2,.3])
                self.assertEqual(panel.overlay.position,(600,280))
            finally:app.close()

    def test_unavailable_game_hides_overlay_without_falling_back_to_monitor(self):
        with tempfile.TemporaryDirectory() as directory, patch('sanctum_panel.game_is_foreground', return_value=False):
            app=App(directory,hotkeys=False)
            try:
                app.ledger.configure(capture_target='auto')
                panel=app.sanctum
                with patch('sanctum_panel.capture_bounds',side_effect=ValueError('Aniimo is minimized.')):
                    panel.show_overlay(header_only=True)
                    self.assertFalse(panel.overlay.visible)
                    self.assertIn('minimized',panel.status.get())
            finally:app.close()
