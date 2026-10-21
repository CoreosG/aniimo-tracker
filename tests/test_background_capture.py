import tempfile
import time
import unittest
import ctypes
from ctypes import wintypes
import tkinter as tk
from unittest.mock import patch
from PIL import Image
from app import App


class BackgroundCaptureTests(unittest.TestCase):
    def test_minimized_inventory_capture_starts_run_and_restores_only_overlay(self):
        with tempfile.TemporaryDirectory() as directory, patch('sanctum_panel.game_is_foreground',return_value=True), \
                patch('sanctum_panel.capture_image',side_effect=lambda *args:Image.new('RGB',(640,480))):
            app=App(directory,hotkeys=False)
            fixture=tk.Tk();fixture.title('Capture focus fixture');fixture.geometry('320x180')
            try:
                app.ledger.configure(capture_target='monitor')
                app.sanctum.always_status.set(True)
                app.update();app.iconify();app.update()
                fixture.update();fixture.lift();fixture.focus_force();fixture.update()
                user=ctypes.windll.user32;user.GetForegroundWindow.restype=wintypes.HWND
                foreground=user.GetForegroundWindow()
                self.assertEqual(fixture.focus_displayof(),fixture)
                def capture(path,*args):Image.new('RGB',(640,480)).save(path)
                def recognize(path,region=None):
                    return '7654.0 K' if region else 'Inventário\nMochila de Aventura\nCofre'
                with patch('app.capture',side_effect=capture),patch('app.recognize',side_effect=recognize):
                    app.capture_image('auto')
                    deadline=time.monotonic()+5
                    while time.monotonic()<deadline:
                        app.update();time.sleep(.01)
                        if app.ledger.active_start() and app.sanctum.overlay.visible and not app.pending_ocr:break
                self.assertIsNotNone(app.ledger.active_start())
                self.assertEqual(app.ledger.active_start()['balance'],7654000)
                self.assertEqual(user.GetForegroundWindow(),foreground)
                self.assertEqual(app.state(),'iconic')
                self.assertTrue(app.sanctum.overlay.visible)
            finally:
                fixture.destroy();app.close()

    def test_button_capture_still_restores_the_window_it_hid(self):
        with tempfile.TemporaryDirectory() as directory, patch('sanctum_panel.game_is_foreground',return_value=False):
            app=App(directory,hotkeys=False)
            try:
                app.update()
                def capture(path,*args):Image.new('RGB',(640,480)).save(path)
                with patch('app.capture',side_effect=capture),patch('app.recognize',return_value='Pontos de ranque\n10000/10200\n+170'):
                    app.capture_button.invoke()
                    self.assertEqual(app.state(),'withdrawn')
                    deadline=time.monotonic()+5
                    while time.monotonic()<deadline:
                        app.update();time.sleep(.01)
                        if not app.busy_capture and not app.auto_busy and not app.pending_ocr:break
                self.assertEqual(app.fields['points'].get(),'170')
                self.assertEqual(app.state(),'normal')
            finally:app.close()

    def test_result_and_overlay_refresh_leave_the_game_fixture_in_front(self):
        with tempfile.TemporaryDirectory() as directory, patch('sanctum_panel.game_is_foreground',return_value=True):
            app=App(directory,hotkeys=False)
            fixture=tk.Tk();fixture.title('Capture focus fixture');fixture.geometry('320x180')
            try:
                app.ledger.configure(capture_target='monitor')
                app.sanctum.always_status.set(True)
                app.tabs.select(app.sanctum_tab);app.update()
                fixture.update();fixture.lift();fixture.focus_force();fixture.update()
                user=ctypes.windll.user32;user.GetForegroundWindow.restype=wintypes.HWND
                foreground=user.GetForegroundWindow()
                self.assertEqual(fixture.focus_displayof(),fixture)
                def capture(path,*args):Image.new('RGB',(640,480)).save(path)
                with patch('app.capture',side_effect=capture),patch('app.recognize',return_value='Pontos de ranque\n10000/10200\n+170'):
                    app.capture_image('auto')
                    deadline=time.monotonic()+5
                    while time.monotonic()<deadline:
                        app.update();time.sleep(.01)
                        if not app.busy_capture and not app.auto_busy and not app.pending_ocr:break
                self.assertEqual(app.fields['points'].get(),'170')
                self.assertEqual(user.GetForegroundWindow(),foreground)
                self.assertEqual(app.tabs.select(),str(app.sanctum_tab))
                self.assertTrue(app.sanctum.overlay.visible)
            finally:
                fixture.destroy();app.close()

    def test_shortcut_result_keeps_minimized_tracker_and_selected_page(self):
        with tempfile.TemporaryDirectory() as directory, patch('sanctum_panel.game_is_foreground',return_value=False):
            app=App(directory,hotkeys=False)
            try:
                app.update()
                app.tabs.select(app.sanctum_tab);app.update()
                app.iconify();app.update()
                self.assertEqual(app.state(),'iconic')
                def capture(path,*args):Image.new('RGB',(640,480)).save(path)
                with patch('app.capture',side_effect=capture),patch('app.recognize',return_value='Pontos de ranque\n10000/10200\n+170'):
                    app.capture_image('auto')
                    deadline=time.monotonic()+5
                    while time.monotonic()<deadline:
                        app.update();time.sleep(.01)
                        if not app.busy_capture and not app.auto_busy and not app.pending_ocr:break
                self.assertEqual(app.fields['points'].get(),'170')
                self.assertEqual(app.state(),'iconic')
                self.assertEqual(app.tabs.select(),str(app.sanctum_tab))
            finally:app.close()
