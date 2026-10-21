"""Screen-only Aniimo window targeting. No game memory, injection or input access."""
from contextlib import contextmanager
import ctypes
from ctypes import wintypes
import ntpath
import os


@contextmanager
def physical_coordinates():
    """Keep client-to-screen coordinates physical even on mixed-DPI desktops."""
    user = ctypes.windll.user32
    previous = None
    setter = getattr(user, 'SetThreadDpiAwarenessContext', None)
    if setter is not None:
        setter.argtypes = [wintypes.HANDLE]
        setter.restype = wintypes.HANDLE
        previous = setter(wintypes.HANDLE(-4))  # PER_MONITOR_AWARE_V2
        if not previous:
            previous = setter(wintypes.HANDLE(-3))  # Older Windows 10 per-monitor context
    try:
        yield
    finally:
        if previous:
            setter(previous)


class NativeWindows:
    """Small Win32 adapter; process identity prevents stale HWND reuse."""
    def __init__(self):
        self.user, self.kernel = ctypes.windll.user32, ctypes.windll.kernel32
        self.user.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
        self.user.GetForegroundWindow.restype = wintypes.HWND
        self.user.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        self.user.IsWindow.argtypes = [wintypes.HWND]
        self.user.IsWindowVisible.argtypes = [wintypes.HWND]
        self.user.IsIconic.argtypes = [wintypes.HWND]
        self.user.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
        self.user.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
        self.kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        self.kernel.OpenProcess.restype = wintypes.HANDLE
        self.kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        self.kernel.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR,
                                                         ctypes.POINTER(wintypes.DWORD)]
        self.kernel.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)]*4

    def read(self, hwnd):
        if not self.user.IsWindow(hwnd) or not self.user.IsWindowVisible(hwnd):
            return None
        title = ctypes.create_unicode_buffer(512)
        self.user.GetWindowTextW(hwnd, title, len(title))
        if not _game_title(title.value):
            return None
        pid = wintypes.DWORD()
        self.user.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if not pid.value or pid.value == os.getpid():
            return None
        process = self.kernel.OpenProcess(0x1000, False, pid.value)
        if not process:
            return None
        try:
            path = ctypes.create_unicode_buffer(32768)
            length = wintypes.DWORD(len(path))
            if not self.kernel.QueryFullProcessImageNameW(process, 0, path, ctypes.byref(length)):
                return None
            created, exited, kernel_time, user_time = (wintypes.FILETIME() for _ in range(4))
            if not self.kernel.GetProcessTimes(process, *(ctypes.byref(value) for value in (created, exited, kernel_time, user_time))):
                return None
            start = (created.dwHighDateTime << 32) | created.dwLowDateTime
        finally:
            self.kernel.CloseHandle(process)
        if not _game_process(path.value):
            return None
        rectangle = wintypes.RECT()
        origin = wintypes.POINT(0, 0)
        if not self.user.GetClientRect(hwnd, ctypes.byref(rectangle)) or not self.user.ClientToScreen(hwnd, ctypes.byref(origin)):
            return None
        target = dict(hwnd=int(hwnd), pid=pid.value, process=path.value.casefold(), created=start)
        return dict(target=target, name=f'Aniimo · PID {pid.value}', minimized=bool(self.user.IsIconic(hwnd)),
                    bbox=(origin.x, origin.y, origin.x+rectangle.right-rectangle.left,
                          origin.y+rectangle.bottom-rectangle.top))

    def list(self):
        result = []
        callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        def visit(hwnd, data):
            record = self.read(hwnd)
            if record is not None:
                result.append(record)
            return True
        callback = callback_type(visit)
        self.user.EnumWindows.argtypes = [callback_type, wintypes.LPARAM]
        self.user.EnumWindows(callback, 0)
        return result


def _game_title(value):
    value = value.strip().casefold()
    return ((value == 'aniimo' or value.startswith(('aniimo ', 'aniimo['))) and
            not any(word in value for word in ('tracker', 'chrome', 'edge', 'codex', 'tools', 'simulator', 'companion', 'nexus')))


def _game_process(path):
    return ntpath.basename(path).casefold() in ('aniimo.exe', 'aniimo-win64-shipping.exe')


def game_windows():
    with physical_coordinates():
        return [dict(name=record['name'], target=record['target']) for record in NativeWindows().list()]


def is_game_foreground(target='auto'):
    with physical_coordinates():
        native = NativeWindows()
        record = native.read(native.user.GetForegroundWindow())
        if record is None or record['minimized']:
            return False
        if target=='auto':
            choices=native.list()
            return len(choices)==1 and choices[0]['target']==record['target']
        return target=='monitor' or record['target']==target


def _fully_visible(bounds, displays):
    """Check the display union, including gaps and negative monitor origins."""
    left, top, right, bottom = bounds
    if right <= left or bottom <= top:
        return False
    edges = sorted({left, right} | {max(left, min(right, edge)) for display in displays for edge in (display[0], display[2])})
    for x1, x2 in zip(edges, edges[1:]):
        if x2 <= x1:
            continue
        intervals = sorted((max(top, display[1]), min(bottom, display[3])) for display in displays
                           if display[0] <= x1 and display[2] >= x2 and display[3] > top and display[1] < bottom)
        covered = top
        for start, end in intervals:
            if start > covered:
                break
            covered = max(covered, end)
        if covered < bottom:
            return False
    return True


def window_bounds(target, displays):
    with physical_coordinates():
        native = NativeWindows()
        if target == 'auto':
            choices = native.list()
            if not choices:
                raise ValueError('Aniimo window not found. Open the game or choose Monitor capture in Settings.')
            if len(choices) != 1:
                raise ValueError('Multiple Aniimo windows found. Select a game window in Settings.')
            record = choices[0]
        elif isinstance(target, dict):
            if (set(target) != {'hwnd', 'pid', 'process', 'created'} or
                    any(type(target.get(key)) is not int or not 0 < target[key] <= 2**64-1 for key in ('hwnd', 'pid', 'created')) or
                    not isinstance(target.get('process'), str) or not _game_process(target['process'])):
                raise ValueError('Selected game window is unavailable. Refresh Capture target in Settings.')
            record = native.read(target['hwnd'])
            if record is None or record['target'] != target:
                raise ValueError('Selected game window is unavailable. Refresh Capture target in Settings.')
        else:
            raise ValueError('Choose Auto, a game window, or Monitor capture in Settings.')
        if record['minimized']:
            raise ValueError('Aniimo is minimized. Restore the game window to capture it.')
        bounds = tuple(record['bbox'])
        if bounds[2]-bounds[0] < 320 or bounds[3]-bounds[1] < 180:
            raise ValueError('Aniimo game area is too small to capture.')
        if not _fully_visible(bounds, displays):
            raise ValueError('Aniimo window is partly off screen. Move the whole game area onto your displays.')
        return bounds
