"""Periodic release notices and a user-initiated portable update handoff."""
import json
import queue
import re
import threading
import time
import webbrowser
import os
import sys
from urllib.request import Request, urlopen
import tkinter as tk
from tkinter import ttk
from version import VERSION
from i18n import tr
from update_install import download_release,start_update_helper,validate_release

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
    result=dict(version=latest,available=available,download_url=expected)
    if 'sha256' in feed or 'size' in feed:
        validate_release(feed)
        result.update(sha256=feed['sha256'],size=feed['size'])
    return result


class UpdatesPanel:
    def __init__(self,app,parent):
        self.app=app;self.path=app.data_dir/'update-state.json';self.events=queue.Queue(maxsize=8);self.busy=False;self.info=None
        self.installing=False;self.pending_install=None;self.closed=False;self.restart_pending=False
        try:self.state=json.loads(self.path.read_text(encoding='utf-8'))
        except (OSError,ValueError):self.state={}
        if not isinstance(self.state,dict):self.state={}
        self.enabled=tk.BooleanVar(value=self.state.get('enabled',True))
        self.was_enabled=self.enabled.get()
        self.automatic=app.hotkeys_enabled
        self.next_check=time.monotonic()+3
        box=ttk.LabelFrame(parent,text='App updates',padding=10);box.pack(fill='x',pady=(0,16))
        ttk.Label(box,text=f'Aniimo Tracker {VERSION}').pack(anchor='w')
        ttk.Checkbutton(box,text='Check on startup and every 30 minutes',variable=self.enabled,command=self.save).pack(anchor='w',pady=5)
        self.status=tk.StringVar(value='Updates use verified GitHub releases. Your run data stays on this PC.')
        ttk.Label(box,textvariable=self.status,wraplength=850,style='Muted.TLabel').pack(anchor='w',pady=5)
        row=ttk.Frame(box);row.pack(anchor='w')
        self.check_button=ttk.Button(row,text='Check for updates',command=self.check);self.check_button.pack(side='left')
        self.download=ttk.Button(row,text='Update & restart',command=self.install_update)

    def save(self):
        if self.enabled.get() and not self.was_enabled:self.next_check=time.monotonic()
        self.was_enabled=self.enabled.get()
        self.state['enabled']=self.enabled.get()
        try:self.path.write_text(json.dumps(self.state),encoding='utf-8')
        except OSError:pass

    def check(self):
        if self.busy or self.installing:return
        self.next_check=time.monotonic()+1800
        self.busy=True;self.status.set(tr('Checking for updates…'));self.check_button.configure(state='disabled')
        def worker():
            try:
                request=Request(FEED,headers={'User-Agent':f'AniimoTracker/{VERSION}'})
                with urlopen(request,timeout=12) as response:
                    content=response.read(16385)
                if len(content)>16384:raise ValueError('Release feed too large')
                if not self.closed:self.events.put(('check',release_info(json.loads(content),VERSION),None))
            except Exception as exc:
                if not self.closed:self.events.put(('check',None,type(exc).__name__))
        threading.Thread(target=worker,daemon=True).start()

    def tick(self):
        if self.closed:return
        if self.automatic and self.enabled.get() and time.monotonic()>=self.next_check:self.check()
        while not self.events.empty():
            kind,value,error=self.events.get_nowait()
            if kind=='progress':
                self.announce('Downloading update… '+f'{round(100*value/error)}%',enabled=False)
                continue
            if kind=='ready':
                self.pending_install=value
                self.announce('Update ready · finishing current capture…',enabled=False)
                continue
            if kind=='install_error':
                self.installing=False;self.pending_install=None
                self.announce('Update failed · try again',enabled=True)
                self.app.status.set('Update failed · '+str(value))
                continue
            self.busy=False;self.check_button.configure(state='normal')
            if error:self.status.set(tr('Could not check for updates. Try again later.'));continue
            self.info=value
            self.state['checked']=time.time();self.save()
            if self.info['available']:
                self.announce('Update available: '+self.info['version'])
                self.download.pack(side='left',padx=8)
            else:
                self.status.set('You have the latest version.');self.download.pack_forget()
                self.app.update_notice_frame.pack_forget()
        if self.pending_install and not (self.app.busy_capture or self.app.auto_busy or self.app.auto_pending or self.app.pending_ocr):
            candidate=self.pending_install;self.pending_install=None
            try:
                self.app.persist_draft()
                start_update_helper(candidate,sys.executable,os.getpid(),self.info['sha256'])
                self.restart_pending=True
                self.announce('Restarting to update…',enabled=False)
                self.app.after(0,self.app.close)
            except Exception as exc:
                self.installing=False
                self.announce('Update failed · try again')
                self.app.status.set('Update failed · '+str(exc))

    def announce(self,text,enabled=True):
        self.status.set(text);self.app.update_notice.set(text)
        action='Update & restart' if getattr(sys,'frozen',False) and self.info and 'sha256' in self.info else 'Download update'
        self.app.update_action.configure(text=action,state='normal' if enabled else 'disabled')
        self.download.configure(text=action,state='normal' if enabled else 'disabled')
        self.app.update_notice_frame.pack(fill='x',pady=(8,0))

    def install_update(self):
        if not self.info or not self.info['available'] or self.installing or self.busy:return
        if not getattr(sys,'frozen',False) or 'sha256' not in self.info:
            self.open_download();return
        self.installing=True
        self.announce('Downloading update… 0%',enabled=False)
        folder=self.app.data_dir/'updates'
        def progress(received,total):
            if self.closed:raise RuntimeError('Tracker closed')
            try:self.events.put_nowait(('progress',received,total))
            except queue.Full:pass
        def worker():
            try:
                folder.mkdir(exist_ok=True)
                candidate=download_release(self.info,folder/'pending.exe',progress)
                if not self.closed:self.events.put(('ready',candidate,None))
            except Exception as exc:
                if not self.closed:self.events.put(('install_error',str(exc),None))
        threading.Thread(target=worker,daemon=True).start()

    def close(self):
        self.closed=True

    def open_download(self):
        if self.info and self.info['available']:webbrowser.open(self.info['download_url'])
