"""Party controls and navigation integration; no network work on the Tk thread."""
import json
import math
import queue
import time
import tkinter as tk
from tkinter import ttk, messagebox
from party_client import PartyClient
from party_protocol import DEFAULT_SERVER, evidence_score, server_url, username
from map_catalog import DIFFICULTIES, layouts_for
from i18n import tr

ERRORS = {'party_full':'Party is full (3 players).', 'party_not_found':'Party not found. Check the code and server.',
          'session_expired':'Party session expired. Join again.', 'server_full':'Server is full. Try again later.',
          'already_connected':'This party session is already connected.', 'invalid_message':'The server rejected a party update.'}


class PartyPanel:
    def __init__(self, app, tab):
        self.app = app
        self.path = app.data_dir/'party-profile.json'
        try: profile = json.loads(self.path.read_text(encoding='utf-8'))
        except (OSError, ValueError): profile = {}
        self.name = tk.StringVar(value=profile.get('username', 'Player'))
        self.saved_name = self.name.get()
        self.mode = tk.StringVar(value=profile.get('mode', 'default'))
        self.address = tk.StringVar(value=profile.get('server', DEFAULT_SERVER))
        self.code = tk.StringVar()
        self.status = tk.StringVar(value='Not in a party')
        self.room_label = tk.StringVar(value='No party · up to 3 players')
        self.map_label = tk.StringVar(value='Waiting for a shared map')
        self.difficulty=tk.StringVar(value=app.sanctum.difficulty.get())
        self.client = PartyClient()
        self.state = None; self.identity = None; self.connected = False; self.connecting = False
        self.received_at = 0.; self.next_publish = 0.; self.observation = None
        self.last_position = None; self.last_context = app.sanctum.session.context_id
        self.done_epoch = 0; self.pending_reset = None; self.last_roster = None
        self.marker_state=None;self.last_locale=None
        canvas=tk.Canvas(tab,bg='#0d1421',highlightthickness=0)
        scrollbar=ttk.Scrollbar(tab,orient='vertical',command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set);scrollbar.pack(side='right',fill='y');canvas.pack(side='left',fill='both',expand=True)
        shell=ttk.Frame(canvas);window=canvas.create_window(0,0,window=shell,anchor='nw')
        shell.bind('<Configure>',lambda e:canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>',lambda e:canvas.itemconfigure(window,width=e.width))
        app.enable_wheel_scroll(canvas,shell)
        ttk.Label(shell,text='Explore together',font=('Segoe UI Semibold',24)).pack(anchor='w')
        ttk.Label(shell,text='Share your map and positions with up to two teammates.',style='Muted.TLabel').pack(anchor='w',pady=(6,20))
        profile_box=ttk.LabelFrame(shell,text='Your profile',padding=16);profile_box.pack(fill='x',pady=(0,12))
        ttk.Label(profile_box,text='Username').grid(row=0,column=0,sticky='w',padx=(0,12))
        ttk.Entry(profile_box,textvariable=self.name,width=26).grid(row=0,column=1,sticky='w')
        ttk.Button(profile_box,text='Save profile',command=self.save_profile).grid(row=0,column=2,padx=12)
        server=ttk.LabelFrame(shell,text='Party server',padding=16);server.pack(fill='x',pady=(0,12))
        self.default_radio=ttk.Radiobutton(server,text='Default · eggheist.banneret.app',variable=self.mode,value='default',command=self.server_changed)
        self.default_radio.pack(anchor='w')
        self.custom_radio=ttk.Radiobutton(server,text='Custom / self-hosted server',variable=self.mode,value='custom',command=self.server_changed)
        self.custom_radio.pack(anchor='w',pady=(8,4))
        self.server_entry=ttk.Entry(server,textvariable=self.address);self.server_entry.pack(fill='x')
        room=ttk.LabelFrame(shell,text='Party',padding=16);room.pack(fill='x')
        buttons=ttk.Frame(room);buttons.pack(fill='x')
        self.create_button=ttk.Button(buttons,text='Create party',style='Accent.TButton',command=lambda:self.connect())
        self.create_button.pack(side='left')
        ttk.Label(buttons,text='or code').pack(side='left',padx=12)
        self.code_entry=ttk.Entry(buttons,textvariable=self.code,width=12);self.code_entry.pack(side='left')
        self.join_button=ttk.Button(buttons,text='Join party',command=lambda:self.connect(join=True));self.join_button.pack(side='left',padx=10)
        self.leave_button=ttk.Button(buttons,text='Leave party',command=self.leave);self.leave_button.pack(side='right')
        row=ttk.Frame(room);row.pack(fill='x',pady=(16,8))
        ttk.Label(row,textvariable=self.room_label,font=('Segoe UI Semibold',13)).pack(side='left')
        self.copy_button=ttk.Button(row,text='Copy code',command=self.copy_code);self.copy_button.pack(side='right')
        self.members=ttk.Treeview(room,columns=('username','presence','role'),show='headings',height=3)
        for key,title in [('username','Username'),('presence','Connection'),('role','Role')]:
            self.members.heading(key,text=title);self.members.column(key,width=180)
        self.members.pack(fill='x',pady=8)
        for color in ('#3df5ff','#ff82cb','#a6fa65'): self.members.tag_configure(color,foreground=color)
        ttk.Label(room,textvariable=self.map_label,wraplength=650).pack(anchor='w',pady=6)
        difficulty_row=ttk.Frame(room);difficulty_row.pack(fill='x',pady=6)
        ttk.Label(difficulty_row,text='Party difficulty').pack(side='left',padx=(0,12))
        self.difficulty_choice=ttk.Combobox(difficulty_row,state='readonly',textvariable=self.difficulty,values=DIFFICULTIES,width=16)
        self.difficulty_choice.pack(side='left');self.difficulty_choice.bind('<<ComboboxSelected>>',lambda e:self.difficulty_changed())
        self.new_button=ttk.Button(room,text='New shared run',command=self.new_run);self.new_button.pack(anchor='w',pady=6)
        ttk.Label(shell,textvariable=self.status,foreground='#79dcc8',wraplength=700).pack(anchor='w',pady=(14,8))
        ttk.Label(shell,text='Only coordinates and map evidence are shared. Screenshots, OCR, loot and run history stay on your PC.',
                  style='Muted.TLabel',wraplength=700).pack(anchor='w')
        self.server_changed();self.controls()

    def server_changed(self):
        self.server_entry.configure(state='normal' if self.mode.get()=='custom' and not self.connecting else 'disabled')

    def save_profile(self):
        try:
            name = username(self.name.get())
            address = server_url(self.address.get()) if self.mode.get()=='custom' else DEFAULT_SERVER
            temporary=self.path.with_suffix('.tmp')
            temporary.write_text(json.dumps(dict(username=name, mode=self.mode.get(), server=address)),encoding='utf-8')
            temporary.replace(self.path)
            self.saved_name=name;self.status.set('Profile saved')
            return True
        except (OSError,ValueError) as exc:
            messagebox.showerror(tr('Party'),tr(str(exc)));return False

    def connect(self, join=False):
        if not self.save_profile():return
        code=self.code.get().strip().upper()
        if join and (len(code)!=8 or not code.isalnum()):
            self.status.set('Enter the 8-character party code.');return
        try:
            self.client.start(DEFAULT_SERVER if self.mode.get()=='default' else self.address.get(),
                              self.saved_name, self.difficulty.get(), code if join else '')
        except ValueError as exc:self.status.set(str(exc));return
        self.connecting=True;self.status.set('Connecting…');self.controls()

    def controls(self):
        active=self.connecting
        for button in (self.create_button,self.join_button,self.code_entry,self.default_radio,self.custom_radio):
            button.configure(state='disabled' if active else 'normal')
        self.leave_button.configure(state='normal' if active else 'disabled')
        self.copy_button.configure(state='normal' if self.state else 'disabled')
        self.new_button.configure(state='normal' if self.connected and self.state and self.state['host']==self.identity else 'disabled')
        host=self.connected and self.state and self.state['host']==self.identity
        self.difficulty_choice.configure(state='readonly' if not active or (host and self.pending_reset is None) else 'disabled')
        self.server_changed()

    def copy_code(self):
        if self.state:
            self.app.clipboard_clear();self.app.clipboard_append(self.state['code']);self.status.set('Party code copied')

    def leave(self):
        self.client.close();self.client=PartyClient();self.state=None;self.identity=None;self.connected=self.connecting=False
        self.observation=None;self.pending_reset=None;self.done_epoch=0
        self.room_label.set('No party · up to 3 players');self.map_label.set('Waiting for a shared map')
        self.members.delete(*self.members.get_children());self.status.set('Not in a party');self.controls()
        self.app.sanctum.overlay_dirty=True;self.app.sanctum.paint()

    def new_run(self):
        if self.connected and self.state and self.identity==self.state['host']:
            if self.pending_reset is not None:return
            self.pending_reset=self.state['epoch'];self.observation=None
            self.client.new_run(self.state['epoch'], self.difficulty.get())
            self.status.set('Starting a new shared run…')
            self.controls()

    def difficulty_changed(self):
        if self.connected:self.new_run()

    def observed_layout(self, layout, reading):
        score=evidence_score(reading)
        if self.connected and self.state and self.pending_reset is None and score>=.75 and self.app.sanctum.session.watching:
            if self.state['epoch']<=self.done_epoch or self.app.sanctum.difficulty.get()!=self.state['difficulty'] or layout not in layouts_for(self.state['difficulty']):return
            self.observation=dict(layout=layout,confidence=score,epoch=self.state['epoch'])

    def clear_shared_map(self):
        panel=self.app.sanctum
        panel.generation+=1;panel.engine=None;panel.player=None;panel.position_time=0
        panel.session.map_confirmed=False;panel.manual_layout=None;panel.last_reading={}
        panel.layout.set('Auto / waiting');panel.map_feedback='Waiting for party map';panel.overlay_dirty=True
        panel.config.update(layout=None,player=None,reading={},map_confirmed=False);panel.write_config();panel.paint()

    def tick(self):
        panel=self.app.sanctum;now=time.monotonic()
        context=panel.session.context_id
        if context!=self.last_context:
            previous=self.last_context;self.last_context=context;self.observation=None;self.last_position=None
            if self.state:
                if previous is not None:self.done_epoch=self.state['epoch']
                if context is not None and self.connected and self.identity==self.state['host']:self.new_run()
        while True:
            try:event=self.client.events.get_nowait()
            except queue.Empty:break
            if not self.connecting:continue
            if event['type']=='error':
                self.leave();self.status.set(ERRORS.get(event['code'],'Party connection failed.'));continue
            if event['type']=='reconnecting':
                self.connected=False;self.status.set('Reconnecting…');self.controls();panel.overlay_dirty=True;continue
            old=self.state
            if event['type']=='welcome':self.identity=event['id'];self.connected=True
            self.state=event['state'];self.received_at=now
            if self.pending_reset is None or self.state['epoch']>self.pending_reset:self.difficulty.set(self.state['difficulty'])
            if old and self.state['epoch']!=old['epoch']:
                self.observation=None;self.last_position=None;self.clear_shared_map()
                self.pending_reset=None
            if old is None and panel.session.watching and panel.engine:
                self.observed_layout(panel.engine.layout,panel.last_reading)
            self.room_label.set(f'{self.state["code"]} · {len(self.state["members"])}/3')
            layout=self.state['layout']
            self.map_label.set(f'{self.state["difficulty"]} {layout} · {self.state["confidence"]:.0%}' if layout else 'Waiting for a shared map')
            self.status.set('Connected · positions sync automatically')
            self.refresh_members()
            panel.overlay_dirty=True;self.controls()
            if self.app.tabs.select()==str(self.app.sanctum_tab):panel.paint()
        if not self.state:return
        state=self.state
        self.refresh_members()
        marker_state=[(p['name'],p['live']) for p in self.markers()]
        if marker_state!=self.marker_state:
            self.marker_state=marker_state;panel.overlay_dirty=True
            if self.app.tabs.select()==str(self.app.sanctum_tab):panel.paint()
        if not self.connected:return
        ready=self.pending_reset is None and state['epoch']>self.done_epoch
        if ready and panel.session.watching:
            if panel.difficulty.get()!=state['difficulty']:
                panel.difficulty.set(state['difficulty']);panel.change_difficulty()
        if ready and state['layout'] is not None and panel.session.watching and panel.assets_ready:
            if not panel.engine or panel.engine.layout!=state['layout'] or not panel.session.map_confirmed:
                panel.generation+=1;panel.player=None;panel.position_time=0;panel.manual_layout=None
                panel.session.confirm_map();panel.accept_layout(state['layout'],{})
                panel.map_feedback=f'{state["difficulty"]} {state["layout"]} · Party map'
                panel.overlay_dirty=True
        if now<self.next_publish:return
        self.next_publish=now+.75
        update=dict(type='update',epoch=state['epoch'])
        own=next((p for p in state['members'] if p['id']==self.identity),None)
        if own and own['username']!=self.saved_name:update['username']=self.saved_name
        if self.observation and state['confidence']>=self.observation['confidence']:self.observation=None
        if ready and self.observation and self.observation['epoch']==state['epoch']:
            update['evidence']={k:self.observation[k] for k in ('layout','confidence')}
        if ready and panel.session.watching and panel.engine and panel.engine.layout==state['layout']:
            if panel.player and panel.position_time and now-panel.position_time<2 and panel.position_time!=self.last_position:
                point=list(panel.player)
                if all(math.isfinite(n) and 0<=n<=100 for n in point):
                    update.update(position=[round(n,2) for n in point],layout=state['layout'],revision=state['revision'])
                    self.last_position=panel.position_time
        elif own and own['position'] is not None:
            update.update(position=None,layout=state['layout'],revision=state['revision'])
        if len(update)>2:self.client.publish(update)

    def refresh_members(self):
        if not self.state:return
        roster=[(p['id'],p['username'],p['online'],p['color'],p['id']==self.state['host']) for p in self.state['members']]
        locale=tr('Host')
        if roster==self.last_roster and locale==self.last_locale:return
        self.last_roster=roster;self.last_locale=locale;self.members.delete(*self.members.get_children())
        for identity,name,online,color,host in roster:
            self.members.insert('', 'end',values=(name,tr('Online' if online else 'Reconnecting…'),tr('Host' if host else 'Member')),tags=(color,))

    def markers(self):
        if not self.state or self.pending_reset is not None or self.state['epoch']<=self.done_epoch:return []
        now=time.monotonic();elapsed=now-self.received_at
        result=[]
        for member in self.state['members']:
            if member['id']==self.identity or not member['position']:continue
            age=member['age']+elapsed
            if age>30:continue
            result.append(dict(position=member['position'],name=member['username'],color=member['color'],live=self.connected and member['online'] and age<3))
        return result

    def own_marker(self):
        color=next((p['color'] for p in self.state['members'] if p['id']==self.identity), '#3df5ff') if self.state else '#3df5ff'
        panel=self.app.sanctum
        matching=self.state and panel.engine and panel.engine.layout==self.state['layout'] and panel.difficulty.get()==self.state['difficulty']
        return dict(player_name=self.saved_name if self.state else None,player_color=color,teammates=self.markers() if matching else [])

    def close(self):self.client.close()
