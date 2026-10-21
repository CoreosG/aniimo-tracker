"""Small cached GitHub release check; downloads are always user initiated."""
import json
import queue
import re
import threading
import time
import webbrowser
from urllib.request import Request, urlopen
import tkinter as tk
from tkinter import ttk
from version import VERSION
from i18n import tr

FEED = 'https://raw.githubusercontent.com/CoreosG/aniimo-tracker/main/updates.json'


def release_info(feed, current):
    def version(value):
        if not isinstance(value,str) or not re.fullmatch(r'\d+\.\d+\.\d+',value):
            raise ValueError('Invalid release version')
        return tuple(map(int,value.split('.')))
    latest=feed['version']
    available=version(latest)>version(current)
    expected=f'https://github.com/CoreosG/aniimo-tracker/releases/download/v{latest}/AniimoTracker.exe'
    if feed.get('download_url')!=expected:raise ValueError('Unexpected release download address')
    return dict(version=latest,available=available,download_url=expected)


class UpdatesPanel:
    def __init__(self,app,parent):
        self.app=app;self.path=app.data_dir/'update-state.json';self.events=queue.Queue();self.busy=False;self.info=None
        try:self.state=json.loads(self.path.read_text(encoding='utf-8'))
        except (OSError,ValueError):self.state={}
        if not isinstance(self.state,dict):self.state={}
        self.enabled=tk.BooleanVar(value=self.state.get('enabled',True))
        box=ttk.LabelFrame(parent,text='App updates',padding=10);box.pack(fill='x',pady=(0,16))
        ttk.Label(box,text=f'Aniimo Tracker {VERSION}').pack(anchor='w')
        ttk.Checkbutton(box,text='Check for updates daily',variable=self.enabled,command=self.save).pack(anchor='w',pady=5)
        self.status=tk.StringVar(value=tr('Updates are downloaded from GitHub. Your run data stays on this PC.'))
        ttk.Label(box,textvariable=self.status,wraplength=850,style='Muted.TLabel').pack(anchor='w',pady=5)
        row=ttk.Frame(box);row.pack(anchor='w')
        self.check_button=ttk.Button(row,text='Check for updates',command=self.check);self.check_button.pack(side='left')
        self.download=ttk.Button(row,text='Download update',command=self.open_download)
        if app.hotkeys_enabled and self.enabled.get() and time.time()-self.state.get('checked',0)>86400:
            app.after(3000,self.check)

    def save(self):
        self.state['enabled']=self.enabled.get()
        try:self.path.write_text(json.dumps(self.state),encoding='utf-8')
        except OSError:pass

    def check(self):
        if self.busy:return
        self.busy=True;self.status.set(tr('Checking for updates…'));self.check_button.configure(state='disabled')
        def worker():
            try:
                request=Request(FEED,headers={'User-Agent':f'AniimoTracker/{VERSION}'})
                with urlopen(request,timeout=12) as response:
                    content=response.read(16385)
                if len(content)>16384:raise ValueError('Release feed too large')
                self.events.put((release_info(json.loads(content),VERSION),None))
            except Exception as exc:self.events.put((None,type(exc).__name__))
        threading.Thread(target=worker,daemon=True).start()

    def tick(self):
        while not self.events.empty():
            self.info,error=self.events.get_nowait();self.busy=False;self.check_button.configure(state='normal')
            if error:self.status.set(tr('Could not check for updates. Try again later.'));continue
            self.state['checked']=time.time();self.save()
            if self.info['available']:
                self.status.set(tr('Update available: ')+self.info['version']);self.download.pack(side='left',padx=8)
                self.app.status.set(tr('Update available: ')+self.info['version']+tr(' · Open Settings to download.'))
            else:self.status.set(tr('You have the latest version.'));self.download.pack_forget()

    def open_download(self):
        if self.info and self.info['available']:webbrowser.open(self.info['download_url'])
