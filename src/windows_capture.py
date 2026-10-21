"""Desktop capture, registered Windows hotkeys, and on-device Windows OCR."""
import asyncio
import ctypes
import threading
import queue
import time
from ctypes import wintypes
from pathlib import Path
from PIL import ImageGrab, Image
from shortcut_keys import DEFAULT_SHORTCUTS, GLOBAL_ACTIONS, ACTION_IDS, compile_shortcuts, matching_actions


def keyboard_modifiers():
    down=lambda vk:bool(ctypes.windll.user32.GetAsyncKeyState(vk)&0x8000)
    return (2 if down(0x11) else 0)|(4 if down(0x10) else 0)|(1 if down(0x12) else 0)|(8 if down(0x5B) or down(0x5C) else 0)


def binding_down(binding):
    return bool(binding and ctypes.windll.user32.GetAsyncKeyState(binding[0])&0x8000 and keyboard_modifiers()&binding[1]==binding[1])


def monitors():
    user32 = ctypes.windll.user32
    class INFO(ctypes.Structure):
        _fields_ = [('size', wintypes.DWORD), ('monitor', wintypes.RECT),
                    ('work', wintypes.RECT), ('flags', wintypes.DWORD),
                    ('device', wintypes.WCHAR * 32)]
    result = []
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HMONITOR,
                                      wintypes.HDC, ctypes.POINTER(wintypes.RECT), wintypes.LPARAM)
    def visit(handle, dc, rect, data):
        info = INFO()
        info.size = ctypes.sizeof(info)
        user32.GetMonitorInfoW(handle, ctypes.byref(info))
        r = info.monitor
        result.append(dict(name=info.device, primary=bool(info.flags & 1),
                           bbox=(r.left, r.top, r.right, r.bottom)))
        return True
    callback = callback_type(visit)
    user32.EnumDisplayMonitors(None, None, callback, 0)
    return sorted(result, key=lambda m: m['name'])


def capture(path, monitor_index=0):
    screens = monitors()
    if not 0 <= monitor_index < len(screens):
        raise ValueError('Selected display is disconnected; choose a display in Settings.')
    im = ImageGrab.grab(bbox=screens[monitor_index]['bbox'], all_screens=True)
    im.save(path)
    return im.size


class Hotkeys:
    def __init__(self,bindings=None):
        self.bindings=bindings if bindings is not None else compile_shortcuts(DEFAULT_SHORTCUTS)
        self.user = ctypes.windll.user32
        self.registered = []
        self.failed = []
        self.events = queue.Queue()
        self.map_events = queue.Queue()
        self.map_hook = None
        self.ready = threading.Event()
        self.thread = threading.Thread(target=self._listen, daemon=True)
        self.thread.start()
        self.ready.wait(3)

    def _listen(self):
        self.thread_id = ctypes.windll.kernel32.GetCurrentThreadId()
        msg = wintypes.MSG()
        self.user.PeekMessageW(ctypes.byref(msg), None, 0, 0, 0)
        # Dedicated message loop: Tk's loop must not consume WM_HOTKEY first.
        for action in GLOBAL_ACTIONS:
            binding=self.bindings[action]
            if not binding:continue
            key,mods=binding;identifier=ACTION_IDS[action]
            if self.user.RegisterHotKey(None, identifier, 0x4000|mods, key):
                self.registered.append(identifier)
            else:
                self.failed.append(identifier)
        # Observe M/Esc without registering or swallowing the game's keys.
        # The native message thread queues taps even while Tk is capturing/rendering.
        callback_type=ctypes.WINFUNCTYPE(ctypes.c_ssize_t,ctypes.c_int,wintypes.WPARAM,wintypes.LPARAM)
        class KeyboardEvent(ctypes.Structure):
            _fields_=[('vkCode',wintypes.DWORD),('scanCode',wintypes.DWORD),('flags',wintypes.DWORD),('time',wintypes.DWORD),('extra',ctypes.c_size_t)]
        held=set()
        watched={binding[0] for action,binding in self.bindings.items() if action not in GLOBAL_ACTIONS and binding}
        self.user.CallNextHookEx.argtypes=[wintypes.HHOOK,ctypes.c_int,wintypes.WPARAM,wintypes.LPARAM]
        self.user.CallNextHookEx.restype=ctypes.c_ssize_t
        self.user.GetForegroundWindow.restype=wintypes.HWND
        self.user.GetWindowTextW.argtypes=[wintypes.HWND,wintypes.LPWSTR,ctypes.c_int]
        def keyboard(code,message,data):
            if code>=0:
                vk=ctypes.cast(data,ctypes.POINTER(KeyboardEvent)).contents.vkCode
                if vk in watched:
                    if message in (0x100,0x104) and vk not in held:
                        held.add(vk)
                        title=ctypes.create_unicode_buffer(512)
                        self.user.GetWindowTextW(self.user.GetForegroundWindow(),title,len(title))
                        name=title.value.strip().lower()
                        if (name=='aniimo' or name.startswith(('aniimo ','aniimo['))) and not any(word in name for word in ('tracker','chrome','edge','codex','tools','simulator','companion','nexus')):
                            for action in matching_actions(self.bindings,vk,keyboard_modifiers(),True):
                                if action in ('map','close_map'):
                                    event=ctypes.cast(data,ctypes.POINTER(KeyboardEvent)).contents
                                    age=((ctypes.windll.kernel32.GetTickCount()&0xffffffff)-event.time)&0xffffffff
                                    stamp=time.monotonic()-age/1000
                                    self.map_events.put((0x4D if action=='map' else 0x1B,stamp))
                                else:self.events.put(ACTION_IDS[action])
                    elif message in (0x101,0x105):held.discard(vk)
            return self.user.CallNextHookEx(None,code,message,data)
        self.keyboard_callback=callback_type(keyboard)
        self.user.SetWindowsHookExW.argtypes=[ctypes.c_int,callback_type,wintypes.HINSTANCE,wintypes.DWORD]
        self.user.SetWindowsHookExW.restype=wintypes.HHOOK
        kernel=ctypes.windll.kernel32
        kernel.GetModuleHandleW.argtypes=[wintypes.LPCWSTR]
        kernel.GetModuleHandleW.restype=wintypes.HMODULE
        self.map_hook=self.user.SetWindowsHookExW(13,self.keyboard_callback,kernel.GetModuleHandleW(None),0)
        self.ready.set()
        try:
            while self.user.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                if msg.message == 0x0312:
                    self.events.put(int(msg.wParam))
        finally:
            if self.map_hook:
                self.user.UnhookWindowsHookEx.argtypes=[wintypes.HHOOK]
                self.user.UnhookWindowsHookEx(self.map_hook)
            for key in self.registered:
                self.user.UnregisterHotKey(None, key)

    def poll_map_keys(self):
        return [vk for vk,stamp in self.poll_map_key_events()]

    def poll_map_key_events(self):
        result=[]
        while not self.map_events.empty():result.append(self.map_events.get_nowait())
        return result

    def poll(self):
        result = []
        while not self.events.empty():
            result.append(self.events.get_nowait())
        return result

    def close(self):
        if hasattr(self, 'thread_id'):
            self.user.PostThreadMessageW(self.thread_id, 0x0012, 0, 0)
            self.thread.join(timeout=2)


async def _recognize(path):
    from winrt.windows.storage import StorageFile, FileAccessMode
    from winrt.windows.graphics.imaging import BitmapDecoder, BitmapPixelFormat, BitmapAlphaMode
    from winrt.windows.media.ocr import OcrEngine
    engine = OcrEngine.try_create_from_user_profile_languages()
    if engine is None:
        raise RuntimeError('Windows OCR language is unavailable. Install a language in Windows Settings.')
    file = await StorageFile.get_file_from_path_async(str(Path(path).resolve()))
    stream = await file.open_async(FileAccessMode.READ)
    try:
        decoder = await BitmapDecoder.create_async(stream)
        bitmap = await decoder.get_software_bitmap_converted_async(BitmapPixelFormat.BGRA8, BitmapAlphaMode.PREMULTIPLIED)
        try:
            result = await engine.recognize_async(bitmap)
            return '\n'.join(line.text for line in result.lines)
        finally:
            bitmap.close()
    finally:
        stream.close()


def recognize(path, region=None):
    source = Path(path)
    with Image.open(source) as original:
        im = original.copy()
    if region:
        w, h = im.size
        im = im.crop(tuple(round(v * (w if i % 2 == 0 else h)) for i, v in enumerate(region)))
        scale = min(3, 2400 / max(im.size))
        im = im.resize((max(1, round(im.width * scale)), max(1, round(im.height * scale))))
    elif max(im.size) > 2400:
        im.thumbnail((2400, 2400))
    temp = source.with_name(source.stem + '.ocr.png')
    try:
        im.convert('RGB').save(temp)
        return asyncio.run(_recognize(temp))
    finally:
        temp.unlink(missing_ok=True)
