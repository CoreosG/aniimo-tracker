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
from player_trails import PlayerTrails

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
        self.warn_unfinished=tk.BooleanVar(value=profile.get('warn_unfinished',True))
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
        self.run_epoch=None;self.pending_context=None;self.notice_pending=None
        self.trails=PlayerTrails()
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
        ttk.Checkbutton(profile_box,text='Warn about unfinished runs',variable=self.warn_unfinished,command=self.save_warning_preference).grid(row=1,column=0,columnspan=3,sticky='w',pady=(12,0))
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
        self.navigation_frame=ttk.Frame(room)
        self.navigation_note=tk.StringVar()
        ttk.Label(self.navigation_frame,textvariable=self.navigation_note,wraplength=650,style='Muted.TLabel').pack(anchor='w')
        self.navigation_button=ttk.Button(self.navigation_frame,command=self.start_navigation)
        difficulty_row=ttk.Frame(room);difficulty_row.pack(fill='x',pady=6)
        ttk.Label(difficulty_row,text='Party difficulty').pack(side='left',padx=(0,12))
        self.difficulty_choice=ttk.Combobox(difficulty_row,state='readonly',textvariable=self.difficulty,values=DIFFICULTIES,width=16)
        self.difficulty_choice.pack(side='left');self.difficulty_choice.bind('<<ComboboxSelected>>',lambda e:self.difficulty_changed())
        self.new_button=ttk.Button(room,text='New shared run',command=self.new_run);self.new_button.pack(anchor='w',pady=6)
        ttk.Label(shell,textvariable=self.status,foreground='#79dcc8',wraplength=700).pack(anchor='w',pady=(14,8))
        ttk.Label(shell,text='Only coordinates and map evidence are shared. Screenshots, OCR, loot and run history stay on your PC.',
                  style='Muted.TLabel',wraplength=700).pack(anchor='w')
        self.server_changed();self.controls()
        self.resume_tick=self.app.after(1000,self.resume_after_update)

    def prepare_update(self):
        if self.connected:return self.client.prepare_update(self.app.data_dir/'party-update.bin')
        return False

    def cancel_update(self):
        self.client.preserve_on_close=False
        try:(self.app.data_dir/'party-update.bin').unlink(missing_ok=True)
        except OSError:pass

    def resume_after_update(self):
        from party_handoff import consume
        session=consume(self.app.data_dir/'party-update.bin')
        if not session or self.connecting:return
        try:
            self.client.start(session['address'],self.saved_name,resume=session)
            self.connecting=True;self.status.set('Rejoining party after update…');self.controls()
        except (ValueError,KeyError,TypeError,AttributeError):self.status.set('Party session expired · join again with the code')

    def server_changed(self):
        self.server_entry.configure(state='normal' if self.mode.get()=='custom' and not self.connecting else 'disabled')

    def save_profile(self):
        try:
            name = username(self.name.get())
            address = server_url(self.address.get()) if self.mode.get()=='custom' else DEFAULT_SERVER
            temporary=self.path.with_suffix('.tmp')
            temporary.write_text(json.dumps(dict(username=name, mode=self.mode.get(), server=address,warn_unfinished=self.warn_unfinished.get())),encoding='utf-8')
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

    def save_warning_preference(self):
        try:
            try:profile=json.loads(self.path.read_text(encoding='utf-8'))
            except (OSError,ValueError):profile={}
            profile['warn_unfinished']=self.warn_unfinished.get()
            temporary=self.path.with_suffix('.tmp');temporary.write_text(json.dumps(profile),encoding='utf-8');temporary.replace(self.path)
            self.notice_pending=None;self.app.set_party_notice('');self.app.sanctum.overlay_dirty=True
        except OSError:self.status.set('Could not save party preferences.')

    def controls(self):
        active=self.connecting
        for button in (self.create_button,self.join_button,self.code_entry,self.default_radio,self.custom_radio):
            button.configure(state='disabled' if active else 'normal')
        self.leave_button.configure(state='normal' if active else 'disabled')
        self.copy_button.configure(state='normal' if self.state else 'disabled')
        self.new_button.configure(state='normal' if self.connected and self.state and self.pending_reset is None else 'disabled')
        host=self.connected and self.state and self.state['host']==self.identity
        self.difficulty_choice.configure(state='readonly' if not active or (host and self.pending_reset is None) else 'disabled')
        self.server_changed()
        self.update_navigation()

    def copy_code(self):
        if self.state:
            self.app.clipboard_clear();self.app.clipboard_append(self.state['code']);self.status.set('Party code copied')

    def update_navigation(self):
        if not self.connected or not self.state:
            self.navigation_frame.pack_forget();return
        panel=self.app.sanctum
        action=None
        if not panel.assets_ready:
            note='Download the map pack to use party maps and positions.'
            action='Open map setup'
        elif self.pending_reset is not None:
            note='Waiting for the new shared run…'
        elif self.state['epoch']<=self.done_epoch:
            note='This shared run has ended. Choose New shared run for the next dungeon.'
        elif panel.session.context_id is None:
            note='Start map tracking to use the party map and share your position.'
            action='Start map tracker'
        elif not panel.session.watching:
            note='Map tracking is paused. Resume to use the party map and share your position.'
            action='Resume map'
        else:
            note='Map tracking active · positions require a local minimap reading.'
        if self.navigation_note.get()!=note:self.navigation_note.set(note)
        if not self.navigation_frame.winfo_manager():self.navigation_frame.pack(fill='x',pady=(4,8),before=self.difficulty_choice.master)
        if action:
            if self.navigation_button.cget('text')!=tr(action):self.navigation_button.configure(text=action)
            if not self.navigation_button.winfo_manager():self.navigation_button.pack(anchor='w',pady=(6,0))
        else:self.navigation_button.pack_forget()

    def start_navigation(self):
        panel=self.app.sanctum
        if not panel.assets_ready:self.app.tabs.select(self.app.sanctum_tab)
        elif self.connected and not panel.session.watching:panel.watch_action()
        self.update_navigation()

    def leave(self):
        self.client.close();self.client=PartyClient();self.state=None;self.identity=None;self.connected=self.connecting=False
        self.observation=None;self.pending_reset=None;self.done_epoch=0
        self.run_epoch=None;self.pending_context=None;self.notice_pending=None;self.app.set_party_notice('')
        self.room_label.set('No party · up to 3 players');self.map_label.set('Waiting for a shared map')
        self.members.delete(*self.members.get_children());self.status.set('Not in a party');self.controls()
        self.app.sanctum.overlay_dirty=True;self.app.sanctum.paint()

    def new_run(self,for_context=None):
        if self.connected and self.state:
            if self.pending_reset is not None:return
            self.pending_reset=self.state['epoch'];self.observation=None
            self.pending_context=for_context
            difficulty=self.difficulty.get() if self.identity==self.state['host'] else self.state['difficulty']
            self.client.new_run(self.state['epoch'], difficulty)
            self.status.set('Starting a new shared run…')
            self.controls()

    def difficulty_changed(self):
        if self.connected:self.new_run()

    def observed_layout(self, layout, reading):
        score=evidence_score(reading,layout)
        if self.connected and self.state and self.pending_reset is None and score>=.75 and self.app.sanctum.session.watching:
            if self.notice_pending and self.state['layout'] is None:return
            if self.state['epoch']<=self.done_epoch or self.app.sanctum.difficulty.get()!=self.state['difficulty'] or layout not in layouts_for(self.state['difficulty']):return
            self.observation=dict(layout=layout,confidence=score,epoch=self.state['epoch'])

    def clear_shared_map(self):
        panel=self.app.sanctum
        panel.generation+=1;panel.engine=None;panel.player=None;panel.position_time=0
        panel.session.map_confirmed=False;panel.manual_layout=None;panel.last_reading={}
        panel.layout.set('Auto / waiting');panel.map_feedback='Waiting for party map';panel.overlay_dirty=True
        panel.config.update(layout=None,player=None,reading={},map_confirmed=False);panel.write_config();panel.paint()

    def sync_context(self):
        panel=self.app.sanctum
        context=panel.session.context_id
        if context!=self.last_context:
            previous=self.last_context;self.last_context=context;self.observation=None;self.last_position=None
            self.app.set_party_notice('');self.notice_pending=None
            if self.state:
                if previous is not None and previous!='map-only':self.done_epoch=self.run_epoch or self.state['epoch']
                self.run_epoch=self.state['epoch'] if context is not None else None
                if context is not None and context!='map-only' and self.connected and self.done_epoch>=self.state['epoch']:self.new_run(for_context=context)

    def tick(self):
        panel=self.app.sanctum;now=time.monotonic()
        self.sync_context();context=panel.session.context_id
        while True:
            try:event=self.client.events.get_nowait()
            except queue.Empty:break
            if not self.connecting:continue
            if event['type']=='error':
                self.leave();self.status.set(ERRORS.get(event['code'],'Party connection failed.'));continue
            if event['type']=='reconnecting':
                self.connected=False
                self.status.set('Reconnecting · party updates stopped' if event.get('reason')=='stale_state' else 'Reconnecting…')
                self.controls();panel.overlay_dirty=True;continue
            old=self.state
            if event.get('id') is not None:self.identity=event['id'];self.connected=True
            self.state=event['state'];self.received_at=now
            if old is None and context is not None:self.run_epoch=self.state['epoch']
            if self.pending_reset is None or self.state['epoch']>self.pending_reset:self.difficulty.set(self.state['difficulty'])
            if old and self.state['epoch']!=old['epoch']:
                self.app.set_party_notice('')
                active=self.app.ledger.active_start()
                if self.pending_context==context and self.pending_reset is not None:
                    self.run_epoch=self.state['epoch']
                elif active and self.run_epoch is not None and self.run_epoch<self.state['epoch'] and self.state.get('started_by',self.state['host'])!=self.identity:
                    self.notice_pending=(self.state['epoch'],active['id'])
                self.observation=None;self.last_position=None;self.clear_shared_map()
                self.pending_reset=None;self.pending_context=None
            if old is None and panel.session.watching and panel.engine:
                self.observed_layout(panel.engine.layout,panel.last_reading)
            self.room_label.set(f'{self.state["code"]} · {len(self.state["members"])}/3')
            layout=self.state['layout']
            self.map_label.set(f'{self.state["difficulty"]} {layout} · {self.state["confidence"]:.0%}' if layout else 'Waiting for a shared map')
            self.status.set('Connected · positions sync automatically')
            self.refresh_members()
            panel.overlay_dirty=True;self.controls()
            if self.app.tabs.select()==str(self.app.sanctum_tab):panel.paint()
        self.update_navigation()
        if not self.state:
            self.update_trails();return
        state=self.state
        if self.notice_pending and state['layout'] is not None:
            active=self.app.ledger.active_start()
            if self.warn_unfinished.get() and active and self.notice_pending==(state['epoch'],active['id']) and not panel.session.standalone:
                self.app.set_party_notice('New party run detected · map updated. Your previous run is unfinished.')
                panel.overlay_dirty=True
            self.notice_pending=None
        self.refresh_members()
        marker_state=[(p['name'],p['live']) for p in self.markers()]
        if marker_state!=self.marker_state:
            self.marker_state=marker_state;panel.overlay_dirty=True
            if self.app.tabs.select()==str(self.app.sanctum_tab):panel.paint()
        if not self.connected:
            self.update_trails();return
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
        self.update_trails()
        if now<self.next_publish:return
        self.next_publish=now+.75
        update=dict(type='update',epoch=state['epoch'])
        own=next((p for p in state['members'] if p['id']==self.identity),None)
        if own and own['username']!=self.saved_name:update['username']=self.saved_name
        if self.observation and state['confidence']>=self.observation['confidence']:self.observation=None
        if ready and self.observation and self.observation['epoch']==state['epoch']:
            update['evidence']={k:self.observation[k] for k in ('layout','confidence')}
        if ready and panel.session.can_navigate and not panel.outdoors and panel.engine and panel.engine.layout==state['layout']:
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

    def update_trails(self):
        panel=self.app.sanctum;now=time.monotonic();state=self.state
        if not panel.player_trails.get() or not panel.session.watching or not panel.engine:
            self.trails.reset(None);return
        shared=state and panel.engine.layout==state['layout'] and panel.difficulty.get()==state['difficulty']
        context=(panel.session.context_id,panel.difficulty.get(),panel.engine.layout,
                 (state['code'],state['epoch'],state['revision']) if shared else None)
        changed=self.trails.reset(context)
        members=state['members'] if shared else []
        own=next((m for m in members if m['id']==self.identity),None)
        identity=self.identity if own else 'local'
        color=own['color'] if own else '#3df5ff'
        point=panel.player if panel.session.can_navigate and not panel.outdoors and panel.position_time and now-panel.position_time<2 else None
        changed=self.trails.observe(identity,color,point,now) or changed
        identities={identity}
        for member in members:
            if member['id']==identity:continue
            identities.add(member['id'])
            point=member['position'] if self.connected and member['online'] and member['age'] is not None and member['age']+now-self.received_at<3 else None
            changed=self.trails.observe(member['id'],member['color'],point,now) or changed
        self.trails.retain(identities)
        if changed:panel.overlay_dirty=True

    def own_marker(self):
        color=next((p['color'] for p in self.state['members'] if p['id']==self.identity), '#3df5ff') if self.state else '#3df5ff'
        panel=self.app.sanctum
        matching=self.state and panel.engine and panel.engine.layout==self.state['layout'] and panel.difficulty.get()==self.state['difficulty']
        return dict(player_name=self.saved_name if self.state else None,player_color=color,teammates=self.markers() if matching else [],
                    trails=self.trails.paths() if panel.player_trails.get() else [])

    def close(self):
        self.app.after_cancel(self.resume_tick)
        self.client.close()
