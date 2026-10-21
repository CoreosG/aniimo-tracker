import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch
from types import SimpleNamespace
from unittest.mock import Mock
from PIL import Image
import windows_capture
import capture_target


class Win32Boundary:
    """Synthetic Win32 return values; target selection still runs real code."""
    def __init__(self, windows):
        self.windows={record['hwnd']:record for record in windows}
        self.user, self.kernel=SimpleNamespace(),SimpleNamespace()
        self.user.IsWindow=Mock(side_effect=lambda hwnd:hwnd in self.windows)
        self.user.IsWindowVisible=Mock(side_effect=lambda hwnd:self.windows[hwnd].get('visible',True))
        self.user.IsIconic=Mock(side_effect=lambda hwnd:self.windows[hwnd].get('minimized',False))
        self.user.GetForegroundWindow=Mock(return_value=next(iter(self.windows),0))
        self.user.GetWindowTextW=Mock(side_effect=self.title)
        self.user.GetWindowThreadProcessId=Mock(side_effect=self.pid)
        self.user.GetClientRect=Mock(side_effect=self.rectangle)
        self.user.ClientToScreen=Mock(side_effect=self.origin)
        self.user.EnumWindows=Mock(side_effect=lambda callback,_:[callback(hwnd,0) for hwnd in self.windows])
        self.user.SetThreadDpiAwarenessContext=Mock(return_value=42)
        self.kernel.OpenProcess=Mock(side_effect=lambda flags,inherit,pid:pid)
        self.kernel.CloseHandle=Mock()
        self.kernel.QueryFullProcessImageNameW=Mock(side_effect=self.path)
        self.kernel.GetProcessTimes=Mock(side_effect=self.created)

    def title(self,hwnd,buffer,length):buffer.value=self.windows[hwnd].get('title','Aniimo');return len(buffer.value)
    def pid(self,hwnd,pointer):pointer._obj.value=self.windows[hwnd]['pid'];return 1
    def path(self,pid,flags,buffer,length):
        buffer.value=next(record for record in self.windows.values() if record['pid']==pid).get('path',r'C:\Games\Aniimo.exe')
        return 1
    def created(self,pid,created,*others):
        value=next(record for record in self.windows.values() if record['pid']==pid).get('created',500)
        created._obj.dwLowDateTime=value;created._obj.dwHighDateTime=0;return 1
    def rectangle(self,hwnd,pointer):
        left,top,right,bottom=self.windows[hwnd]['bbox']
        pointer._obj.left=0;pointer._obj.top=0;pointer._obj.right=right-left;pointer._obj.bottom=bottom-top;return 1
    def origin(self,hwnd,pointer):
        left,top,*_=self.windows[hwnd]['bbox'];pointer._obj.x=left;pointer._obj.y=top;return 1

    def patched(self):
        return patch.object(capture_target.ctypes,'windll',SimpleNamespace(user32=self.user,kernel32=self.kernel))


class WindowCaptureTests(TestCase):
    def test_foreground_identity_distinguishes_two_games_and_auto_rejects_ambiguity(self):
        boundary=Win32Boundary([dict(hwnd=101,pid=201,bbox=(0,0,1280,720)),
                               dict(hwnd=102,pid=202,bbox=(0,0,1280,720))])
        with boundary.patched():
            first,second=windows_capture.game_windows()
            self.assertFalse(windows_capture.game_is_foreground())
            self.assertTrue(windows_capture.game_is_foreground(first['target']))
            self.assertFalse(windows_capture.game_is_foreground(second['target']))
            boundary.user.GetForegroundWindow.return_value=102
            self.assertFalse(windows_capture.game_is_foreground(first['target']))
            self.assertTrue(windows_capture.game_is_foreground(second['target']))

    def test_window_selection_uses_only_game_executable_and_returns_physical_client_area(self):
        boundary=Win32Boundary([
            dict(hwnd=101,pid=201,bbox=(120,80,1400,800)),
            dict(hwnd=102,pid=202,bbox=(0,0,1920,1080),title='Aniimo tools',path=r'C:\Chrome\chrome.exe'),
            dict(hwnd=103,pid=203,bbox=(0,0,1920,1080),title='Aniimo',path=r'C:\Chrome\chrome.exe'),
            dict(hwnd=104,pid=204,bbox=(0,0,1920,1080),title='Aniimo Tracker',path=r'C:\Aniimo.exe')])
        with boundary.patched(),patch('windows_capture.monitors',return_value=[dict(bbox=(0,0,1920,1080))]):
            choices=windows_capture.game_windows()
            self.assertEqual([choice['target']['hwnd'] for choice in choices],[101])
            self.assertEqual(windows_capture.capture_bounds(target=choices[0]['target']),(120,80,1400,800))
            self.assertEqual(windows_capture.capture_bounds(),(120,80,1400,800))
            self.assertGreaterEqual(boundary.user.SetThreadDpiAwarenessContext.call_count,6)

    def test_reused_window_handle_minimization_and_clipping_are_rejected(self):
        boundary=Win32Boundary([dict(hwnd=101,pid=201,bbox=(0,0,1280,720))])
        with boundary.patched(),patch('windows_capture.monitors',return_value=[dict(bbox=(0,0,1920,1080))]):
            target=windows_capture.game_windows()[0]['target']
            boundary.windows[101]['created']=501
            with self.assertRaises(ValueError):windows_capture.capture_bounds(target=target)
            boundary.windows[101]['created']=500
            boundary.windows[101]['minimized']=True
            with self.assertRaises(ValueError):windows_capture.capture_bounds()
            boundary.windows[101]['minimized']=False
            boundary.windows[101]['bbox']=(-30,0,1250,720)
            with self.assertRaises(ValueError):windows_capture.capture_bounds()

    def test_auto_fails_closed_when_missing_or_ambiguous_but_monitor_is_explicit(self):
        for records in ([],[dict(hwnd=101,pid=201,bbox=(0,0,1280,720)),dict(hwnd=102,pid=202,bbox=(0,0,1280,720))]):
            boundary=Win32Boundary(records)
            with boundary.patched(),patch('windows_capture.monitors',return_value=[dict(bbox=(0,0,1920,1080))]):
                with self.assertRaises(ValueError):windows_capture.capture_bounds()
                self.assertEqual(windows_capture.capture_bounds(target='monitor'),(0,0,1920,1080))

    def test_two_displays_support_negative_origins_and_reject_a_gap_inside_the_window(self):
        boundary=Win32Boundary([dict(hwnd=101,pid=201,bbox=(-3840,0,0,2160))])
        with boundary.patched(),patch('windows_capture.monitors',return_value=[dict(bbox=(-3840,0,0,2160)),dict(bbox=(0,0,1920,1080))]):
            self.assertEqual(windows_capture.capture_bounds(),(-3840,0,0,2160))
        boundary.windows[101]['bbox']=(-200,100,1000,820)
        with boundary.patched(),patch('windows_capture.monitors',return_value=[dict(bbox=(-1920,0,-100,1080)),dict(bbox=(0,0,1920,1080))]):
            with self.assertRaises(ValueError):windows_capture.capture_bounds()

    def test_game_client_crop_excludes_desktop_at_720p_and_4k(self):
        for bounds in ((120, 80, 1400, 800), (-3840, 0, 0, 2160)):
            with self.subTest(bounds=bounds), tempfile.TemporaryDirectory() as directory:
                image = Image.new('RGB', (bounds[2]-bounds[0], bounds[3]-bounds[1]), '#123456')
                with patch('windows_capture.capture_bounds', return_value=bounds), \
                        patch('windows_capture.game_is_foreground', return_value=True), \
                        patch('windows_capture.ImageGrab.grab', return_value=image) as grab:
                    output = Path(directory)/'capture.png'
                    self.assertEqual(windows_capture.capture(output, target='auto'), image.size)
                    with Image.open(output) as saved:
                        self.assertEqual(saved.size, image.size)
                    grab.assert_called_once_with(bbox=bounds, all_screens=True)

    def test_auto_capture_never_grabs_the_desktop_when_another_app_covers_the_game(self):
        with patch('windows_capture.capture_bounds', return_value=(0, 0, 1280, 720)), \
                patch('windows_capture.game_is_foreground', return_value=False), \
                patch('windows_capture.ImageGrab.grab') as grab, tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                windows_capture.capture(Path(directory)/'capture.png')
            grab.assert_not_called()
