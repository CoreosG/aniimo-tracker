"""Non-activating map overlay; click-through unless explicitly unlocked to move."""
import ctypes
from ctypes import wintypes
import tkinter as tk
from PIL import ImageTk
from i18n import tr


class MapOverlay:
    def __init__(self,app,on_position=None):
        self.on_position=on_position
        self.movable=False
        self.position=None
        self.drag_origin=None
        self.window=tk.Toplevel(app)
        self.window.withdraw()
        self.window.overrideredirect(True)
        self.window.configure(bg='#000001')
        self.window.attributes('-topmost',True)
        self.window.attributes('-transparentcolor','#000001')
        self.canvas=tk.Canvas(self.window,bg='#000001',highlightthickness=0)
        self.canvas.pack(fill='both',expand=True)
        self.canvas.bind('<ButtonPress-1>',self.start_drag)
        self.canvas.bind('<B1-Motion>',self.drag)
        self.canvas.bind('<ButtonRelease-1>',self.finish_drag)
        self.window.update_idletasks()
        user=ctypes.windll.user32
        user.GetParent.restype=wintypes.HWND
        self.hwnd=user.GetParent(self.window.winfo_id())
        get=user.GetWindowLongPtrW;set_=user.SetWindowLongPtrW
        get.argtypes=[wintypes.HWND,ctypes.c_int];get.restype=ctypes.c_ssize_t
        set_.argtypes=[wintypes.HWND,ctypes.c_int,ctypes.c_ssize_t];set_.restype=ctypes.c_ssize_t
        self.set_long=set_
        user.IsWindowVisible.argtypes=[wintypes.HWND]
        user.IsWindowVisible.restype=wintypes.BOOL
        # LAYERED + TRANSPARENT makes all mouse input pass through; NOACTIVATE
        # ensures displaying the overlay cannot steal keyboard/game focus.
        self.styles=get(self.hwnd,-20)|0x80000|0x20|0x8000000|0x80
        set_(self.hwnd,-20,self.styles)
        user.SetWindowDisplayAffinity.argtypes=[wintypes.HWND,wintypes.DWORD]
        self.capture_excluded=bool(user.SetWindowDisplayAffinity(self.hwnd,0x11))

    def set_movable(self,value):
        self.movable=bool(value)
        if self.movable:self.position=None
        self.drag_origin=None
        styles=self.styles & ~0x20 if self.movable else self.styles
        self.set_long(self.hwnd,-20,styles)
        # Give the whole square a hit surface while arranging, including map gaps.
        self.window.attributes('-transparentcolor','' if self.movable else '#000001')
        self.canvas.configure(cursor='fleur' if self.movable else '')

    def start_drag(self,event):
        if self.movable:
            self.drag_origin=(event.x_root,event.y_root,self.window.winfo_x(),self.window.winfo_y())

    def drag(self,event):
        if self.movable and self.drag_origin:
            mx,my,x,y=self.drag_origin
            self.position=(x+event.x_root-mx,y+event.y_root-my)
            # Win32 uses absolute virtual-screen coordinates. Tk's negative
            # geometry offsets mean distance from the right/bottom edge.
            ctypes.windll.user32.SetWindowPos(self.hwnd,None,*self.position,0,0,0x15)

    def finish_drag(self,event):
        self.drag(event)
        self.drag_origin=None
        if self.movable and self.position is not None and self.on_position:
            self.on_position(self.position)

    @property
    def visible(self):
        # Windows can hide an overlay independently (owner minimize, shell,
        # display changes). A cached boolean prevented it ever being restored.
        return bool(ctypes.windll.user32.IsWindowVisible(self.hwnd))

    def show(self,image,bbox,opacity=.9,label='',details=''):
        x,y,_,_=bbox
        if self.movable and self.position is not None:x,y=self.position
        self.position=(x,y)
        self.window.geometry(f'{image.width}x{image.height}')
        self.window.attributes('-alpha',max(.1,min(1.,float(opacity))))
        self.photo=ImageTk.PhotoImage(image)
        self.canvas.delete('all')
        picture=self.canvas.create_image(0,0,image=self.photo,anchor='nw')
        if self.movable and (image.height>1 or not label):label='Drag to move · use Lock overlay when done'
        if details:
            state,_,values=details.partition('\n')
            if state:label=(label+' · ' if label else '')+state
            if values:label+='\n'+values
        text=self.canvas.create_text(12,10,text=tr(label),fill='#a4ffe1',anchor='nw',width=image.width-24,font=('Segoe UI',9,'bold'))
        bottom=self.canvas.bbox(text)[3]+8
        background=self.canvas.create_rectangle(4,4,image.width-4,bottom,fill='#15232c',outline='#68e1b9')
        self.canvas.tag_lower(background,text)
        # Keep the header above the map, rather than covering rooms/portals.
        self.canvas.coords(picture,0,bottom+6)
        height=image.height+bottom+6
        self.window.geometry(f'{image.width}x{height}')
        self.window.deiconify()
        self.window.update_idletasks()
        # This overlay must survive minimizing the tracker that created it.
        self.set_long(self.hwnd,-8,0)
        user=ctypes.windll.user32
        # ShowWindow(SW_SHOWNOACTIVATE), rather than deiconify/focus/lift.
        user.ShowWindow.argtypes=[wintypes.HWND,ctypes.c_int]
        user.SetWindowPos.argtypes=[wintypes.HWND,wintypes.HWND,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,wintypes.UINT]
        user.ShowWindow(self.hwnd,4)
        user.SetWindowPos(self.hwnd,wintypes.HWND(-1),x,y,image.width,height,0x10|0x40)

    def hide(self):
        if self.visible:
            ctypes.windll.user32.ShowWindow(self.hwnd,0)

    def close(self):
        self.window.destroy()
