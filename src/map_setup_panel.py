"""Explicit first-use map download, kept off the UI thread."""
import queue
import threading
from tkinter import ttk
from asset_paths import ASSETS,maps_ready,recognition_ready
from i18n import tr


class MapSetupPanel:
    def __init__(self,panel,parent):
        self.panel=panel;self.events=queue.Queue();self.busy=False
        panel.assets_ready=maps_ready()
        self.box=ttk.LabelFrame(parent,text='Local map pack',padding=12)
        if not panel.assets_ready or not recognition_ready():self.box.pack(fill='x',pady=(0,12))
        self.label=ttk.Label(self.box,text='Download maps once from AniimoTools and MOANIIMO. Run tracking works without them.',wraplength=900)
        if panel.assets_ready:self.label.configure(text='Update map pack to enable automatic minimap identification. Existing M recognition still works.')
        self.label.pack(anchor='w',pady=(0,8))
        self.button=ttk.Button(self.box,text='Update map pack' if panel.assets_ready else 'Download map pack',command=self.download,style='Accent.TButton');self.button.pack(anchor='w')

    def download(self):
        if self.busy:return
        self.busy=True;self.button.configure(state='disabled')
        self.label.configure(text=tr('Downloading maps…'))
        def worker():
            try:
                from setup_maps import install,install_recognition
                download=install_recognition if self.panel.assets_ready else install
                download(ASSETS,progress=lambda message:self.events.put(('progress',message)))
                self.events.put(('done',None))
            except Exception as exc:self.events.put(('error',str(exc)))
        threading.Thread(target=worker,daemon=True).start()

    def tick(self):
        while not self.events.empty():
            kind,message=self.events.get_nowait()
            if kind=='progress':self.label.configure(text=tr(message));continue
            self.busy=False;self.button.configure(state='normal')
            self.panel.assets_ready=maps_ready()
            if kind=='done' and self.panel.assets_ready:
                self.panel.recognition_key=None
                self.box.pack_forget();self.panel.status.set(tr('Map pack ready. Open the game map to begin.'))
            else:self.label.configure(text=tr('Map download failed. Retry; your run history was not changed.')+'\n'+(message or '')[:200])
