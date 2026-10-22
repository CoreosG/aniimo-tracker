from asset_paths import ASSETS
"""Local map preview, run-scoped recognition and click-through game overlay."""
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import time
import webbrowser
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageGrab, ImageTk
from sanctum import Detector, LAYOUTS, WatchSession, SITE_URL
from windows_capture import monitors, binding_down, capture_bounds, capture_image
from map_engine import MapEngine,MapLibrary
from minimap_recognition import MinimapRecognizer
from map_overlay import MapOverlay
from shortcut_keys import ObservedKeyTaps
from map_catalog import DIFFICULTIES,layouts_for
from i18n import tr
from party_protocol import evidence_score


def app_is_foreground():
    user=ctypes.windll.user32
    user.GetForegroundWindow.restype=wintypes.HWND
    pid=wintypes.DWORD()
    user.GetWindowThreadProcessId(user.GetForegroundWindow(),ctypes.byref(pid))
    return pid.value==os.getpid()


def game_is_foreground(target='auto'):
    from windows_capture import game_is_foreground as foreground_game
    return foreground_game(target)


class SanctumPanel:
    @property
    def map_open(self):return self.session.map_open

    @map_open.setter
    def map_open(self,value):self.session.map_open=bool(value)

    def __init__(self, app, tab):
        self.app, self.tab = app, tab
        self.folder = app.data_dir / 'sanctum'
        self.folder.mkdir(exist_ok=True)
        self.config_path = self.folder / 'control.json'
        try:
            self.config = json.loads(self.config_path.read_text(encoding='utf-8'))
        except (OSError,ValueError):
            self.config = {}
        self.config.update(shutdown=False)
        self.standalone=bool(self.config.get('standalone_watch',False))
        self.context_serial=0
        self.map_rescan_pending=False
        self.map_taps,self.close_taps=ObservedKeyTaps(),ObservedKeyTaps()
        difficulty=self.config.get('difficulty','Chaos')
        self.difficulty=tk.StringVar(value=difficulty if difficulty in DIFFICULTIES else 'Chaos')
        self.route_goal=tk.StringVar(value=self.config.get('route_goal','keys'))
        self.route_rooms=tk.StringVar(value=str(self.config.get('route_rooms',1)))
        self.route_exit=tk.StringVar(value=self.config.get('route_exit','nearest'))
        self.legend=tk.BooleanVar(value=self.config.get('legend',False))
        self.player_trails=tk.BooleanVar(value=self.config.get('player_trails',True))
        self.egg_count=tk.StringVar(value=str(self.config.get('route_eggs',1)))
        self.icon_vars={name:tk.BooleanVar(value=self.config.get('icons',{}).get(name,name not in ('chests','monsters'))) for name in ('keys','eggs','trials','chests','monsters')}
        self.detector = Detector(self.folder / 'calibration',self.difficulty.get())
        self.session = WatchSession(self.config.get('enabled',True))
        self.session.run_id = -1
        self.messages = queue.Queue()
        self.busy, self.m_down, self.scan_until, self.next_scan = False, False, 0., 0.
        self.map_open, self.escape_down = False, False
        self.generation = 0
        self.process = None
        self.last_image = None
        self.last_reading = {}
        self.reading_time = 0
        self.status_checked = 0
        self.manual_layout = None
        self.last_proposal, self.stable_count = None, 0
        self.engine,self.player,self.position_time = None,None,0
        self.maps=MapLibrary(self.difficulty.get())
        self.recognizer=None;self.recognition_key=None
        self.outdoors=False;self.outdoor_votes=0
        self.app.auto_maps.difficulty=self.difficulty.get()
        self.next_minimap,self.overlay_dirty = 0,True
        self.last_capture_status=''
        self.capture_frame_bounds=None
        self.next_bounds_check=0
        self.map_feedback='Identifying map…'
        self.capture_status=tk.BooleanVar(value=self.config.get('capture_status',True))
        self.always_status=tk.BooleanVar(value=self.config.get('always_status',False))
        self.automatic_minimap=tk.BooleanVar(value=self.config.get('automatic_minimap',True))
        self.unconfirmed_trials=tk.BooleanVar(value=self.config.get('unconfirmed_trials',False))
        self.next_screen_probe=0
        self.overlay_enabled=tk.BooleanVar(value=self.config.get('overlay_enabled',True))
        self.preview_overlay=tk.BooleanVar(value=False)
        self.last_previewing=False
        self.preview_position_dirty=False
        self.adjust_render_id=None
        self.adjust_save_id=None
        self.opacity=tk.DoubleVar(value=self.config.get('opacity',90))
        self.overlay_size=tk.DoubleVar(value=self.config.get('overlay_size',650))
        self.zoom=tk.DoubleVar(value=self.config.get('zoom',1.0))
        self.follow=tk.BooleanVar(value=self.config.get('follow',True))
        self.refresh_mode=tk.StringVar(value='Low CPU (1.5s)' if self.config.get('position_interval')==1.5 else 'Normal (0.7s)')
        self.enabled = tk.BooleanVar(value=self.session.enabled)
        self.party = app.budget_party
        self.keys = tk.StringVar(value=str(self.config.get('route_keys',2)))
        self.layout = tk.StringVar(value='Auto / waiting')
        self.status = tk.StringVar(value='Start a run and open the game map inside the Sanctum. Recognition is automatic.')
        self.route_status = tk.StringVar(value='Local maps and routes · no website needed')
        self.build()
        self.overlay=MapOverlay(app,self.save_overlay_position)
        self.sync_run()

    def build(self):
        from map_setup_panel import MapSetupPanel
        self.map_setup=MapSetupPanel(self,self.tab)
        top=ttk.Frame(self.tab);top.pack(fill='x',pady=(0,16))
        titles=ttk.Frame(top);titles.pack(side='left')
        ttk.Label(titles,text='SANCTUM NAVIGATOR',foreground='#8da8c4',font=('Segoe UI Semibold',9)).pack(anchor='w')
        ttk.Label(titles,text='Map & routes',font=('Segoe UI Semibold',22)).pack(anchor='w',pady=(3,0))
        actions=ttk.Frame(self.tab);actions.pack(fill='x',pady=(0,14))
        self.tracking_button=ttk.Button(actions,text='Resume map',command=self.watch_action,style='Accent.TButton')
        self.tracking_button.pack(side='left',padx=(0,12))
        self.overlay_check=ttk.Checkbutton(actions,text='Show overlay',variable=self.overlay_enabled,command=self.toggle_overlay)
        self.overlay_check.pack(side='left',padx=(0,12))
        self.move_button=ttk.Button(actions,text='Move overlay',command=self.toggle_move);self.move_button.pack(side='left')
        self.stop_only_button=ttk.Button(actions,text='Stop map-only session',command=self.stop_map_only,style='Card.TButton')
        self.stop_only_button.pack(side='right')
        status_options=ttk.Frame(self.tab);status_options.pack(fill='x',pady=(0,12))
        self.persistent_check=ttk.Checkbutton(status_options,text='Persistent status bar',variable=self.always_status,command=self.save_preferences)
        self.persistent_check.pack(side='left',padx=(0,12))
        ttk.Label(status_options,text='Keep run status and shortcut hints visible between runs.',foreground='#9aabc3',wraplength=400).pack(side='left')
        body=ttk.Frame(self.tab);body.pack(fill='both',expand=True)
        side=ttk.Frame(body);side.pack(side='left',fill='y',padx=(0,18))
        scroll=tk.Canvas(side,width=285,bg='#0d1421',highlightthickness=0)
        scrollbar=ttk.Scrollbar(side,orient='vertical',command=scroll.yview)
        scroll.configure(yscrollcommand=scrollbar.set);scrollbar.pack(side='right',fill='y');scroll.pack(side='left',fill='both',expand=True)
        controls=ttk.Frame(scroll);window=scroll.create_window(0,0,window=controls,anchor='nw')
        controls.bind('<Configure>',lambda e:scroll.configure(scrollregion=scroll.bbox('all')))
        scroll.bind('<Configure>',lambda e:scroll.itemconfigure(window,width=e.width))
        self.app.enable_wheel_scroll(scroll,controls)
        self.map_section=tk.StringVar(value='Route')
        ttk.Label(controls,text='MAP SETTINGS',foreground='#9aabc3',font=('Segoe UI Semibold',9)).pack(anchor='w',pady=(0,6))
        section_tabs=ttk.Frame(controls);section_tabs.pack(fill='x',pady=(0,12))
        section_tabs.columnconfigure((0,1),weight=1,uniform='sections')
        self.section_buttons={}
        for index,name in enumerate(('Route','Icons','Overlay','Tools')):
            button=ttk.Radiobutton(section_tabs,text=name,value=name,variable=self.map_section,command=self.show_map_section,style='Chip.TRadiobutton')
            button.grid(row=index//2,column=index%2,sticky='ew',padx=2,pady=2)
            self.section_buttons[name]=button
        self.map_sections={name:ttk.Frame(controls) for name in ('Route','Icons','Overlay','Tools')}
        self.map_sections['Route'].pack(fill='x')
        section=self.map_sections['Route']
        def card(title):
            frame=ttk.Frame(section,style='Panel.TFrame',padding=15);frame.pack(fill='x',pady=(0,12))
            ttk.Label(frame,text=title,style='Panel.TLabel',foreground='#9aabc3',font=('Segoe UI Semibold',9)).pack(anchor='w',pady=(0,10))
            return frame
        difficulty=card('DIFFICULTY')
        row=ttk.Frame(difficulty,style='Panel.TFrame');row.pack(fill='x')
        for index,name in enumerate(DIFFICULTIES):
            ttk.Radiobutton(row,text=name,variable=self.difficulty,value=name,command=self.change_difficulty,style='Chip.TRadiobutton').grid(row=index//2,column=index%2,sticky='ew',padx=2,pady=3)
        row.columnconfigure((0,1),weight=1)
        route=card('ROUTE GOAL')
        for name,value in [('Key doors','keys'),('Egg nests','eggs'),('Eggs + key doors','both'),('Rich rooms','rich'),('Sanctums / trials','trials'),('Map only · no route','none')]:
            ttk.Radiobutton(route,text=name,variable=self.route_goal,value=value,command=self.save_preferences,style='Panel.TRadiobutton').pack(anchor='w',pady=3)
        counts=ttk.Frame(route,style='Panel.TFrame');counts.pack(fill='x',pady=(12,2))
        self.count_spins={}
        for title,var,maximum in [('Key rooms',self.keys,3),('Egg nests',self.egg_count,8)]:
            box=ttk.Frame(counts,style='Panel.TFrame');box.pack(side='left',expand=True,fill='x')
            ttk.Label(box,text=title+' (up to)',style='Panel.TLabel',foreground='#9aabc3').pack(anchor='w')
            spin=ttk.Spinbox(box,textvariable=var,from_=1,to=maximum,width=5,state='readonly',command=self.save_preferences)
            spin.pack(anchor='w',pady=(5,0));self.count_spins['keys' if title=='Key rooms' else 'eggs']=spin
        ttk.Label(route,text='Rich rooms / trials (up to)',style='Panel.TLabel',foreground='#9aabc3').pack(anchor='w',pady=(10,3))
        self.room_spin=ttk.Spinbox(route,textvariable=self.route_rooms,from_=1,to=4,width=5,state='readonly',command=self.save_preferences)
        self.room_spin.pack(anchor='w')
        exits=card('PREFERRED EXIT')
        for title,value in [('Nearest exit','nearest'),('Orange portal','orange'),('Blue portal','blue')]:
            ttk.Radiobutton(exits,text=title,variable=self.route_exit,value=value,command=self.save_preferences,style='Panel.TRadiobutton').pack(anchor='w',pady=3)
        ttk.Label(exits,text='Routes always begin at both entrances.',style='Panel.TLabel',wraplength=245,foreground='#9aabc3').pack(anchor='w',pady=(8,0))
        section=self.map_sections['Icons']
        layers=card('MAP ICONS')
        for title,name in [('Key doors','keys'),('Egg nests','eggs'),('Sanctums / trials','trials'),('Chest rooms','chests'),('Monsters','monsters')]:
            ttk.Checkbutton(layers,text=title,variable=self.icon_vars[name],command=self.save_preferences,style='Panel.TCheckbutton').pack(anchor='w',pady=3)
        ttk.Checkbutton(layers,text='Include unconfirmed trials (?)',variable=self.unconfirmed_trials,command=self.save_preferences,style='Panel.TCheckbutton').pack(anchor='w',pady=3)
        ttk.Checkbutton(layers,text='Map legend',variable=self.legend,command=self.save_preferences,style='Panel.TCheckbutton').pack(anchor='w',pady=3)
        ttk.Checkbutton(layers,text='Player trails',variable=self.player_trails,command=self.save_preferences,style='Panel.TCheckbutton').pack(anchor='w',pady=3)
        section=self.map_sections['Overlay']
        options=card('OVERLAY DISPLAY')
        self.advanced=options
        ttk.Checkbutton(options,text='Live overlay preview',variable=self.preview_overlay,command=self.tick,style='Panel.TCheckbutton').pack(anchor='w',pady=6)
        ttk.Checkbutton(options,text='Capture / save status in overlay',variable=self.capture_status,command=self.save_preferences,style='Panel.TCheckbutton').pack(anchor='w',pady=6)
        for title,var,lo,hi in [('Opacity',self.opacity,15,100),('Overlay size',self.overlay_size,350,950),('Zoom',self.zoom,1,3)]:
            row=ttk.Frame(options,style='Panel.TFrame');row.pack(fill='x',pady=(9,0))
            ttk.Label(row,text=title,style='Panel.TLabel').pack(side='left')
            value=tk.StringVar()
            def update_value(*_,var=var,title=title,value=value):
                value.set(f'{var.get():.0f}%' if title=='Opacity' else f'{var.get():.0f} px' if title=='Overlay size' else f'{var.get():.1f}×')
            var.trace_add('write',update_value);update_value()
            ttk.Label(row,textvariable=value,style='Panel.TLabel',foreground='#79dcc8').pack(side='right')
            ttk.Scale(options,variable=var,from_=lo,to=hi,command=self.adjust_overlay).pack(fill='x',pady=4)
        ttk.Checkbutton(options,text='Follow player',variable=self.follow,command=self.save_preferences,style='Panel.TCheckbutton').pack(anchor='w',pady=6)
        ttk.Label(options,text='Position updates',style='Panel.TLabel').pack(anchor='w',pady=(10,4))
        refresh_choice=ttk.Combobox(options,textvariable=self.refresh_mode,values=('Normal (0.7s)','Low CPU (1.5s)'),state='readonly')
        refresh_choice.pack(fill='x');refresh_choice.bind('<<ComboboxSelected>>',lambda event:self.save_preferences())
        ttk.Button(options,text='Reset overlay position',command=self.reset_overlay_position).pack(fill='x',pady=(12,0))
        section=self.map_sections['Tools']
        options=card('TOOLS & CALIBRATION')
        ttk.Checkbutton(options,text='Identify from minimap',variable=self.automatic_minimap,command=self.save_preferences).pack(anchor='w',pady=6)
        ttk.Checkbutton(options,text='Party budget · carry 1 key',variable=self.party,command=self.save_party).pack(anchor='w',pady=6)
        for title,command in [('Set minimap area',self.set_minimap),('Import map image',self.import_map),('Calibrate markers',self.calibrate),('Open local simulator',self.open_simulator)]:
            ttk.Button(options,text=title,command=command).pack(fill='x',pady=3)
        workspace=ttk.Frame(body,style='Panel.TFrame',padding=18);workspace.pack(side='left',fill='both',expand=True)
        bar=ttk.Frame(workspace,style='Panel.TFrame');bar.pack(fill='x')
        ttk.Label(bar,text='LAYOUT',style='Panel.TLabel',foreground='#9aabc3',font=('Segoe UI Semibold',9)).pack(side='left')
        self.layout_choice=ttk.Combobox(bar,textvariable=self.layout,values=['Auto / waiting']+[str(n) for n in layouts_for(self.difficulty.get())],state='readonly',width=24)
        self.layout_choice.pack(side='right');self.layout_choice.bind('<<ComboboxSelected>>',lambda e:self.select_layout())
        ttk.Label(workspace,textvariable=self.status,style='Panel.TLabel',foreground='#79dcc8',wraplength=660).pack(anchor='w',pady=(12,8))
        self.preview=tk.Canvas(workspace,height=380,bg='#101826',highlightthickness=0)
        self.preview.pack(fill='both',expand=True,pady=8);self.preview.bind('<Configure>',lambda e:self.paint())
        self.preview.bind('<Button-1>',self.inspect_room)
        self.room_details=tk.StringVar(value='Click a room icon for details.')
        ttk.Label(workspace,textvariable=self.room_details,style='Panel.TLabel',foreground='#edf5f5',wraplength=660).pack(anchor='w',pady=(4,0))
        self.preview.create_text(250,150,text=tr('Open the game map to begin\nOr choose a layout to explore routes'),fill='#8c9db5',font=('Segoe UI',13),justify='center',tags='empty')
        ttk.Label(workspace,textvariable=self.route_status,style='Panel.TLabel',foreground='#9aabc3',wraplength=660).pack(anchor='w',pady=(8,4))
        self.instructions_label=ttk.Label(workspace,style='Panel.TLabel',foreground='#70849e',wraplength=660)
        self.instructions_label.pack(anchor='w',pady=(6,0))
        workspace.bind('<Configure>',lambda event:[child.configure(wraplength=max(220,event.width-36)) for child in workspace.winfo_children() if isinstance(child,ttk.Label)])
        self.update_shortcut_hints()
        for name,spin in self.count_spins.items():
            spin.configure(state='readonly' if self.route_goal.get() in (name,'both') else 'disabled')

    def show_map_section(self):
        for frame in self.map_sections.values():frame.pack_forget()
        self.map_sections[self.map_section.get()].pack(fill='x')
        if self.map_section.get()!='Overlay':self.preview_overlay.set(False)
        self.tick()

    def reset_overlay_position(self):
        self.config.pop('overlay_position',None)
        self.overlay.position=None
        self.preview_overlay.set(True)
        self.overlay_dirty=True
        self.write_config();self.tick()

    def change_difficulty(self):
        self.session.inside_dungeon=False
        difficulty=self.difficulty.get()
        self.detector.difficulty=self.maps.difficulty=self.app.auto_maps.difficulty=difficulty
        self.context_serial+=1;self.generation+=1
        self.session.map_confirmed=False;self.map_open=False;self.map_rescan_pending=False
        self.engine,self.player,self.position_time=None,None,0
        self.manual_layout=None;self.last_reading={};self.last_image=None
        self.layout.set('Auto / waiting');self.layout_choice.configure(values=['Auto / waiting']+[str(n) for n in layouts_for(difficulty)])
        self.config.update(layout=None,reading={},player=None,map_confirmed=False)
        self.scan_until=0;self.next_screen_probe=0;self.overlay.hide();self.preview.delete('all')
        self.status.set(f'{difficulty} · {len(layouts_for(difficulty))} layouts · open the game map or preview a layout.')
        self.update_shortcut_hints();self.save_preferences()

    def render_options(self):
        party=self.app.party.own_marker() if hasattr(self.app,'party') else {}
        return dict(goal=self.route_goal.get(),eggs=int(self.egg_count.get()),icons={k:v.get() for k,v in self.icon_vars.items()},unconfirmed_trials=self.unconfirmed_trials.get(),rooms=int(self.route_rooms.get()),exit=self.route_exit.get(),legend=self.legend.get(),**party)

    def update_shortcut_hints(self):
        key=self.app.shortcut_hint('map')
        self.instructions_label.configure(text=f'Minimap identifies your layout automatically. Press {key} to confirm or correct it.')
        self.overlay_check.configure(text=f'Show overlay ({self.app.shortcut_hint("overlay")})')

    def save_overlay_position(self,position):
        self.config['overlay_position']=list(position)
        self.write_config()

    def toggle_overlay(self):
        if not self.overlay_enabled.get():
            self.overlay.set_movable(False)
            self.move_button.configure(text='Move overlay')
            self.overlay.hide()
        self.save_preferences()

    def toggle_move(self):
        moving=not self.overlay.movable
        self.overlay.set_movable(moving)
        self.move_button.configure(text='Lock overlay' if moving else 'Move overlay')
        if moving:self.overlay_enabled.set(True)
        self.save_preferences()
        self.tick()

    def watch_action(self):
        if not self.app.ledger.active_start() and not self.standalone:
            self.standalone=True
            self.enabled.set(True);self.session.enable(True)
            self.config['paused_context']=None
            self.sync_run();self.save_preferences()
            self.status.set(f'Map tracker only · open the game map inside {self.difficulty.get()}. No run or stats are recorded.' if self.standalone else 'Map tracker stopped. No run or stats were changed.')
            self.app.refresh()
            return
        if self.session.watching:self.end_watch()
        else:self.resume_watch()
        self.app.update_run_status()

    def stop_map_only(self):
        if not self.standalone:return
        self.standalone=False
        self.sync_run();self.save_preferences();self.app.refresh()
        self.status.set('Map-only session stopped. No run or stats were changed.')

    def update_tracking_button(self):
        if not hasattr(self,'tracking_button'):return
        self.tracking_button.configure(text=('Pause map' if self.session.watching else 'Resume map') if self.session.context_id is not None else 'Start map tracker',state='normal')
        if hasattr(self,'stop_only_button'):self.stop_only_button.configure(state='normal' if self.standalone else 'disabled')

    def save_preferences(self):
        self.config.update(enabled=self.enabled.get(),party=self.party.get(),route_keys=int(self.keys.get()),
            standalone_watch=self.standalone,difficulty=self.difficulty.get(),route_goal=self.route_goal.get(),route_eggs=int(self.egg_count.get()),route_rooms=int(self.route_rooms.get()),route_exit=self.route_exit.get(),legend=self.legend.get(),icons={k:v.get() for k,v in self.icon_vars.items()},
            overlay_enabled=self.overlay_enabled.get(),opacity=round(self.opacity.get()),overlay_size=round(self.overlay_size.get()),
            zoom=self.zoom.get(),follow=self.follow.get(),capture_status=self.capture_status.get(),always_status=self.always_status.get(),unconfirmed_trials=self.unconfirmed_trials.get(),automatic_minimap=self.automatic_minimap.get(),player_trails=self.player_trails.get())
        self.config['position_interval']=1.5 if self.refresh_mode.get()=='Low CPU (1.5s)' else .7
        self.overlay_dirty=True
        if hasattr(self,'count_spins'):
            for name,spin in self.count_spins.items():spin.configure(state='readonly' if self.route_goal.get() in (name,'both') else 'disabled')
        if hasattr(self,'room_spin'):self.room_spin.configure(state='readonly' if self.route_goal.get() in ('rich','trials') else 'disabled')
        self.update_tracking_button()
        self.write_config()
        if hasattr(self,'preview'):self.paint()

    def adjust_overlay(self,_=None):
        self.preview_overlay.set(True)
        self.overlay_dirty=True
        if self.adjust_render_id is None:
            self.tick()
            self.adjust_render_id=self.app.after(33,self.render_adjustment)
        if self.adjust_save_id is not None:self.app.after_cancel(self.adjust_save_id)
        self.adjust_save_id=self.app.after(200,self.save_adjustment)

    def render_adjustment(self):
        self.adjust_render_id=None
        self.tick()

    def save_adjustment(self):
        self.adjust_save_id=None
        self.save_preferences()

    def write_config(self):
        temp = self.config_path.with_suffix('.tmp')
        temp.write_text(json.dumps(self.config),encoding='utf-8')
        temp.replace(self.config_path)

    def save_party(self):
        self.app.ledger.configure(budget_party=self.party.get())
        self.save_preferences();self.app.refresh()

    def toggle(self):
        self.session.enable(self.enabled.get())
        self.config['paused_run'] = None
        self.scan_until = 0
        self.map_open = False
        self.config['reading'] = {}
        self.generation += 1
        self.save_preferences()
        self.status.set('Watch armed for this run; open the game map in Aniimo.' if self.session.watching else 'Map watch off.')

    def sync_run(self):
        active = self.app.ledger.active_start()
        run_id = active['id'] if active else None
        if run_id is not None:self.standalone=False
        context_id=run_id if run_id is not None else 'map-only' if self.standalone else None
        if self.session.context_id != context_id:
            self.outdoors=False;self.outdoor_votes=0
            restore=context_id is not None and context_id!='map-only' and self.config.get('watch_context',self.config.get('run_id'))==context_id and self.config.get('map_confirmed',False)
            saved_layout=self.config.get('layout') if restore else None
            saved_reading=self.config.get('reading',{}) if restore else {}
            saved_player=self.config.get('player') if restore else None
            self.session.begin(run_id,standalone=self.standalone)
            self.context_serial+=1
            self.generation += 1
            self.scan_until = 0
            self.map_rescan_pending=False
            self.map_open = False
            self.map_feedback='Identifying map…'
            self.manual_layout = None
            self.last_reading = {}
            self.engine,self.player,self.position_time = None,None,0
            self.last_proposal,self.stable_count=None,0
            self.overlay.hide()
            self.config.update(layout=None,reading={},run_id=run_id,watch_context=context_id,standalone_watch=self.standalone,map_confirmed=False)
            self.layout.set('Auto / waiting')
            if context_id is not None and self.config.get('paused_context',self.config.get('paused_run'))==context_id:
                self.session.end()
            if saved_layout in layouts_for(self.difficulty.get()):
                self.session.confirm_map()
                self.accept_layout(saved_layout,saved_reading)
                self.session.inside_dungeon=False
                if saved_player:self.player=saved_player
                self.config.update(reading=saved_reading,player=self.player)
                self.overlay_dirty=True
            self.write_config()
            self.status.set(('Run active · watch armed. Open the game map with both portals visible.' if self.session.watching else
                'Run active · tracking paused. Click Resume map.') if run_id is not None else
                (f'Map tracker only · open the game map inside {self.difficulty.get()}.' if self.standalone else 'No active run · start a run or start the map tracker.'))

        self.update_tracking_button()

    def end_watch(self):
        self.session.end()
        self.scan_until = 0
        self.map_rescan_pending=False
        self.map_open = False
        self.generation += 1
        self.overlay.hide()
        self.config['paused_run'] = self.session.run_id
        self.config['paused_context'] = self.session.context_id
        self.config['reading'] = {}
        self.write_config()
        self.update_tracking_button()
        self.status.set('Map tracking paused. Use the same toggle to resume; the detected layout is retained.')

    def resume_watch(self):
        self.sync_run()
        if self.session.context_id is None:
            self.status.set('No tracked run is active. Start a run from the dashboard before resuming map tracking.')
            return
        self.session.resume()
        self.session.inside_dungeon=False
        self.enabled.set(True)
        self.generation+=1
        self.scan_until,self.next_scan,self.next_minimap,self.next_screen_probe=0,0,0,0
        self.map_rescan_pending=False
        self.position_time=0;self.last_proposal,self.stable_count=None,0
        self.overlay_dirty=True;self.config['paused_run']=None;self.config['paused_context']=None
        self.save_preferences()
        self.status.set('Tracking resumed on the same run. Open the game map once if the layout needs reacquiring.')

    def game_focused(self):
        target=self.app.ledger.settings().get('capture_target','auto')
        # Keep the existing no-argument hook/QA seam for automatic and explicit
        # monitor modes, while a chosen HWND must match its full saved identity.
        return game_is_foreground(target) if isinstance(target,dict) else game_is_foreground()

    def poll_map_keys(self):
        """Handle visibility-critical input without capture, recognition or rendering."""
        now = time.monotonic()
        down = binding_down(self.app.shortcut_specs['map'])
        escape = binding_down(self.app.shortcut_specs['close_map'])
        in_game = self.game_focused()
        if self.app.hk and hasattr(self.app.hk,'poll_map_key_events'):
            queued=self.app.hk.poll_map_key_events()
        else:
            queued=[(vk,now) for vk in self.app.hk.poll_map_keys()] if self.app.hk else []
        if not in_game:queued=[]
        # Polling remains a fallback even with a hook installed. Native event
        # timestamps pair both observations of one press, including late events.
        map_presses=self.map_taps.presses([stamp for vk,stamp in queued if vk==0x4D],in_game and down,now)
        escape_pressed=self.close_taps.presses([stamp for vk,stamp in queued if vk==0x1B],in_game and escape,now)>0
        for _ in range(map_presses if self.session.watching or self.overlay.movable else 0):
            self.session.map_key_pressed()
            self.generation+=1
            self.map_rescan_pending=self.session.watching
            self.map_feedback='Identifying map…'
            self.overlay_dirty=True
            self.scan_until,self.next_scan = (now+(30 if self.map_open else 3) if self.session.watching else 0),now+.5
            self.overlay.hide()
            if self.map_open and self.session.watching and self.overlay_enabled.get() and in_game:
                self.show_overlay(header_only=True)
            self.status.set('Map key received · freshly checking the layout from both portals…')
            self.app.status.set(self.status.get())
        if self.session.watching and escape_pressed:
            self.map_open,self.scan_until = False,0
            self.map_rescan_pending=False
            self.generation += 1
            self.overlay_dirty=True
            self.config['reading'] = {}
            self.write_config()
        self.m_down = down
        self.escape_down = escape

    def tick(self):
        self.map_setup.tick()
        self.poll_map_keys()
        details=self.app.overlay_run_status() if self.capture_status.get() else ''
        if details!=self.last_capture_status:
            self.last_capture_status=details;self.overlay_dirty=True
        now = time.monotonic()
        in_game = self.game_focused()
        if in_game and now>=self.next_bounds_check:
            self.next_bounds_check=now+.2
            try:self.capture_geometry()
            except ValueError as exc:
                self.overlay.hide();in_game=False
                if self.session.watching:self.status.set(str(exc))
        if self.process is not None and now-self.status_checked>2:
            self.status_checked = now
            try:
                if self.process.poll() is not None:
                    error = self.folder/'viewer-error.txt'
                    self.route_status.set('Simulator closed. '+(error.read_text(encoding='utf-8')[:180] if error.exists() else 'Open BOTH entrance routes to reopen it.'))
                else:
                    report = json.loads((self.folder/'viewer-status.json').read_text(encoding='utf-8'))
                    views = report.get('views',[])
                    if self.config.get('layout') and len(views)==2 and all(v and v.get('ready') and v.get('layout')==self.config['layout'] for v in views):
                        self.route_status.set(f"Live routes ready · layout {self.config['layout']} · {views[0]['keys']} key rooms · orange AND blue entrances · nearest exit")
                    elif not self.config.get('layout'):
                        self.route_status.set('Simulator open · waiting for a detected or manually selected layout')
            except (OSError,ValueError,KeyError):
                pass
        capturing=self.app.busy_capture or self.app.auto_busy or not self.assets_ready
        if self.session.watching and in_game and (self.scan_until>now or self.map_open) and now>=self.next_scan and not self.busy and not capturing:
            self.scan()
            self.next_scan = now+1.2
        if self.map_rescan_pending and now>=self.scan_until:self.map_rescan_pending=False
        # Pixel recovery is independent of the keyboard hook. An unconfirmed
        # watch must still see M when a tap was lost or M was already open.
        if self.session.watching and not self.session.map_confirmed and in_game and now>=self.next_screen_probe and not self.busy and not capturing:
            self.scan()
            self.next_screen_probe=now+1.2
        if self.session.can_track_minimap and not self.map_open and not self.map_rescan_pending and in_game and now>=self.next_minimap and not self.busy and not capturing:
            self.scan(minimap=True)
            self.next_minimap=now+(self.config.get('position_interval',.7) if self.engine else 3.)
        while not self.messages.empty():
            generation,image,reading,error = self.messages.get_nowait()
            self.busy = False
            if generation != self.generation:
                continue
            if error:
                self.map_feedback='Map capture failed';self.overlay_dirty=True
                self.status.set('Map capture failed: '+error)
                continue
            self.map_rescan_pending=False
            self.overlay_dirty=True
            if reading.get('map_screen') is True:
                self.session.observe_screen('full_map')
            elif reading.get('map_screen') is False:
                # Closing the map restores the overlay even when there is no
                # confident minimap position. Key toggles are only hints.
                self.map_open=False
                self.scan_until=0
            if reading.get('outside'):
                self.session.inside_dungeon=False
                self.last_reading={}
                self.outdoors=True;self.outdoor_votes=2
                self.player=None;self.position_time=0
                self.map_feedback='Outside dungeon';self.status.set(self.map_feedback)
                continue
            if reading.get('minimap'):
                automatic=reading.get('automatic') or {}
                if automatic.get('kind')=='outside':
                    self.session.inside_dungeon=False
                    self.last_reading={}
                    self.outdoor_votes=min(2,self.outdoor_votes+1)
                    self.player=None;self.position_time=0
                    if self.outdoor_votes>=2:self.outdoors=True
                    self.map_feedback='Outside dungeon · waiting for minimap'
                    self.status.set(self.map_feedback)
                    continue
                if automatic:
                    self.outdoor_votes=0
                    if automatic.get('kind')=='match' and (not self.session.map_confirmed or not self.session.inside_dungeon or self.outdoors):
                        self.outdoors=False
                        self.accept_layout(automatic['layout'],automatic)
                        self.player=self.engine.position_from_reference(automatic['reference_position'])
                        self.position_time=now
                        self.map_feedback=f'{self.difficulty.get()} {self.engine.layout} · Minimap confirmed'
                        self.status.set(self.map_feedback)
                    elif automatic.get('kind')=='match' and self.engine and automatic['layout']==self.engine.layout:
                        self.remember_evidence(self.engine.layout,automatic)
                    elif not self.session.map_confirmed:
                        self.status.set(automatic.get('reason','Comparing corridors'))
                if not self.session.can_track_minimap:
                    continue
                if reading.get('match') and self.session.can_navigate and not self.outdoors:
                    self.session.observe_screen('minimap')
                    self.scan_until=0
                    if not self.engine:
                        self.accept_layout(reading['match']['layout'],{})
                    self.player=reading['match']['player'];self.position_time=now;self.overlay_dirty=True
                    self.config.update(player=self.player,layout=self.engine.layout)
                    match=reading['match']
                    evidence=f'{match["confidence"]:.0%} corridor match' if match.get('method')=='corridors' else f'{match["inliers"]} matched features'
                    self.status.set(f'Layout {self.engine.layout} · following minimap · {evidence}')
                    self.preview_position_dirty=True
                continue
            candidates = reading.get('candidates',[])
            if candidates and not reading.get('explicit'):
                self.session.observe_screen('full_map')
            if candidates or not self.detector.calibrated or reading.get('explicit'):
                self.last_image,self.last_reading = image,reading
                image.save(self.folder/'last-map.png')
                self.reading_time = time.time()
                self.paint()
            if not self.detector.calibrated:
                self.scan_until = 0
                self.status.set('Map captured. Click Calibrate markers once; automatic detection starts after that.')
                continue
            if candidates:
                self.scan_until = now+5
                chosen = self.manual_layout if self.manual_layout in candidates else candidates[0] if len(candidates)==1 else None
                if chosen is not None:
                    # Both portals plus a unique layout are sufficient after an M
                    # event; requiring another scan loses brief map openings.
                    self.config.update(layout=chosen,reading={k:reading[k] for k in ('orange','blue','player') if k in reading})
                    self.layout.set(str(chosen))
                    self.accept_layout(chosen,reading)
                    self.app.status.set(f'{self.difficulty.get()} layout {chosen} confirmed. Close the game map to show the overlay.')
                else:
                    self.map_feedback='Map not identified'
                    self.config.update(layout=None,reading={})
                    self.write_config()
                self.status.set(f"Layout {chosen if chosen else 'choose layout'} · " +
                    ('player marker visible' if 'player' in reading else 'player marker not confirmed') +
                    (' · partly covered '+', '.join(reading['occluded_portals'])+' entrance matched' if reading.get('occluded_portals') else '') +
                    ' · last full-map reading')
            else:
                if reading.get('map_screen'):self.map_feedback='Map not identified'
                self.last_proposal,self.stable_count = None,0
                self.config['reading'] = {}
                self.write_config()
                self.status.set(reading.get('reason','Map not visible; waiting for the map key.'))
                if reading.get('requested') or reading.get('map_screen'):
                    self.app.status.set('Map not confirmed: '+self.status.get())
        live=now-self.position_time<2
        if self.position_time and not live:
            self.position_time=0;self.overlay_dirty=True
            self.status.set(f'Layout {self.engine.layout} · position paused · open the game map to refresh or set minimap area')
        arranging=self.overlay.movable and self.overlay_enabled.get()
        on_map_tab=self.app.tabs.select()==str(self.app.sanctum_tab)
        if self.preview_position_dirty and on_map_tab and app_is_foreground():
            self.paint();self.preview_position_dirty=False
        if not on_map_tab:self.preview_overlay.set(False)
        previewing=self.assets_ready and self.preview_overlay.get() and on_map_tab and app_is_foreground()
        if previewing!=self.last_previewing:
            self.last_previewing=previewing;self.overlay_dirty=True
        waiting=self.session.watching and self.session.context_id is not None and not self.session.map_confirmed
        idle_bar=self.always_status.get() and not self.session.watching
        header_only=self.map_open or self.map_rescan_pending or idle_bar
        show=previewing or (self.overlay_enabled.get() and (arranging or (in_game and (idle_bar or waiting or (self.session.watching and header_only) or (self.session.can_track_minimap and self.engine)))))
        if not show:self.overlay.hide()
        elif self.overlay_dirty or not self.overlay.visible:
            self.show_overlay(header_only=header_only and not previewing,preview=previewing)
            self.overlay_dirty=False

    def show_overlay(self,header_only=False,preview=False):
        screens=monitors()
        if not screens:return
        index=self.app.ledger.settings()['monitor']
        selected=screens[index] if 0<=index<len(screens) else next((m for m in screens if m.get('primary')),screens[0])
        screen=selected['bbox']
        settings=self.app.ledger.settings()
        target=settings.get('capture_target','auto')
        if target!='monitor':
            try:screen=self.capture_geometry()
            except ValueError as exc:
                if not preview:
                    self.overlay.hide();self.status.set(str(exc));return
        size=round(self.overlay_size.get())
        position=self.overlay.position if self.overlay.movable and self.overlay.position else self.config.get('overlay_position',[screen[2]-size-20,screen[1]+70])
        if target=='monitor' or preview:
            screen=next((m['bbox'] for m in screens if m['bbox'][0]<=position[0]<m['bbox'][2] and m['bbox'][1]<=position[1]<m['bbox'][3]),screen)
        size=max(150,min(size,screen[2]-screen[0]-32,screen[3]-screen[1]-100))
        position=[max(screen[0]+12,min(position[0],screen[2]-size-12)),max(screen[1]+12,min(position[1],screen[3]-size-88))]
        if self.overlay.movable:self.overlay.position=tuple(position)
        engine=(self.engine or (self.maps.model(layouts_for(self.difficulty.get())[0]) if preview else None)) if self.assets_ready else None
        draw_map=not header_only and engine is not None and (preview or not self.outdoors and self.session.can_navigate)
        live=time.monotonic()-self.position_time<2
        player=(self.player or [50,50]) if preview else self.player
        image=engine.render((size,size),int(self.keys.get()),None,player,self.zoom.get(),self.follow.get(),live or preview,**self.render_options()) if draw_map else Image.new('RGB',(size,1),'#000001')
        label='Overlay preview' if preview else self.map_feedback if header_only else f'{self.difficulty.get()} {engine.layout}' if draw_map else ''
        if (not self.capture_status.get() or self.session.standalone) and not draw_map and not header_only:label=f'Waiting for map · {self.app.shortcut_hint("map")} to confirm'
        if not preview and self.session.watching and not self.session.inside_dungeon:
            shared=self.app.party.state if hasattr(self.app,'party') else None
            if self.outdoors:label='Outside dungeon'
            elif shared and shared.get('layout') is not None:label='Waiting for dungeon'
            if shared and shared.get('layout') is not None:label+=f' · {shared["difficulty"]} {shared["layout"]}'
        if not self.assets_ready:label='Map pack required · download in the Map tab'
        details=self.app.overlay_run_status() if self.capture_status.get() and not preview else ''
        if self.always_status.get() and not self.app.ledger.active_start() and not preview:
            start=self.app.shortcut_hint('capture')+' start run' if self.app.shortcuts['capture'] else 'Start run in tracker'
            ready,_=self.app.result_ready()
            actions=[]
            if self.app.shortcuts['capture']:actions.append(self.app.shortcut_hint('capture')+' capture')
            if ready and self.app.shortcuts['save']:actions.append(self.app.shortcut_hint('save')+' save')
            pending=any(self.app.fields[k].get().strip() or k in self.app.draft_images for k in ('money','points')) or self.app.pending_ocr or self.app.auto_busy or self.app.auto_pending or self.app.busy_capture
            if ready:
                if not details:details='Points ready\n'+' · '.join(actions)
            elif not pending:details=start
            elif not details:details='Result pending\n'+' · '.join(actions)
        if self.always_status.get() and self.app.ledger.active_start() and not preview and not details:
            details='Run active'
        if self.always_status.get() and not self.session.watching and not preview:
            label='Map tracking paused' if self.session.context_id is not None else 'Ready'
        # Map feedback already describes the current view; omit duplicate
        # waiting/run text so the bar stays at two short lines.
        if header_only and details and self.session.watching:details='\n'+details.partition('\n')[2]
        self.overlay.show(image,(*position,0,0),self.opacity.get()/100,label,details=details)

    def capture_geometry(self):
        settings=self.app.ledger.settings()
        target=settings.get('capture_target','auto')
        bounds=capture_bounds(settings['monitor'],target)
        space='monitor' if target=='monitor' else 'client'
        if self.config.get('capture_space','monitor')!=space:
            self.config.pop('minimap_region',None)
            self.config['capture_space']=space
            self.capture_frame_bounds=None
            self.generation+=1
            self.write_config()
        previous=self.capture_frame_bounds
        if previous and space=='client' and previous!=bounds:
            delta=(bounds[0]-previous[0],bounds[1]-previous[1])
            if 'overlay_position' in self.config:
                self.config['overlay_position']=[self.config['overlay_position'][0]+delta[0],self.config['overlay_position'][1]+delta[1]]
            if self.overlay.position:
                self.overlay.position=(self.overlay.position[0]+delta[0],self.overlay.position[1]+delta[1])
            self.overlay_dirty=True
        self.capture_frame_bounds=bounds
        return bounds

    def scan(self, explicit=False,minimap=False):
        if not self.assets_ready:
            self.status.set('Download the map pack in Map & routes first.');return
        if self.busy:
            return
        settings=self.app.ledger.settings()
        monitor,target=settings['monitor'],settings.get('capture_target','auto')
        try:self.capture_geometry()
        except ValueError as exc:
            self.status.set(str(exc))
            return
        self.busy = True
        generation = self.generation
        requested=self.map_rescan_pending or explicit
        if self.overlay.visible and not self.overlay.capture_excluded:
            self.overlay.hide();self.app.update_idletasks()
        engine=self.engine
        detector=self.detector
        maps=self.maps
        confirmed=self.session.map_confirmed
        local_inside=self.session.inside_dungeon
        recognition_key=(self.context_serial,self.generation,self.difficulty.get(),self.automatic_minimap.get())
        if self.recognition_key!=recognition_key:
            self.recognition_key=recognition_key
            self.recognizer=MinimapRecognizer.from_assets(ASSETS,layouts_for(self.difficulty.get())) or MinimapRecognizer({})
        recognizer=self.recognizer
        outdoors=self.outdoors
        automatic_enabled=self.automatic_minimap.get()
        map_key=self.app.shortcut_hint('map')
        region=self.config.get('minimap_region')
        previous=list(self.player) if self.player and time.monotonic()-self.position_time<3 else None
        def work():
            try:
                # Display capture can wait on the graphics driver. Keep it off
                # Tk's thread so map-key input can hide the overlay immediately.
                image = capture_image(monitor,target).convert('RGB')
                map_screen=detector.is_map_screen(image)
                if map_screen or explicit:
                    reading=detector.detect(image)
                else:
                    automatic=recognizer.observe(image,region,identify=automatic_enabled and bool(recognizer.references))
                    if automatic.get('kind')=='searching' and (not automatic_enabled or not recognizer.references):
                        automatic['reason']=f'Update map pack for automatic minimap recognition · {map_key} still works' if automatic_enabled else f'Automatic minimap recognition off · press {map_key} to confirm'
                    outside=automatic.get('kind')=='outside'
                    match=engine.match_minimap(image,region,previous=previous) if confirmed and local_inside and engine and not outside and not outdoors else None
                    if not match and confirmed and engine and not outdoors and automatic.get('kind')=='match' and automatic['layout']==engine.layout:
                        match=dict(player=engine.position_from_reference(automatic['reference_position']),confidence=automatic['confidence'],method='corridors',inliers=0)
                    reading=dict(minimap=True,match=match,automatic=automatic)
                reading['map_screen']=map_screen
                reading['requested']=requested
                reading['explicit'] = explicit
                self.messages.put((generation,image,reading,None))
            except Exception as exc:
                self.messages.put((generation,None,None,str(exc)))
        threading.Thread(target=work,daemon=True).start()

    def capture_button(self):
        # Explicit one-shot capture also works outside a tracked run for calibration.
        self.app.withdraw()
        def capture_and_restore():
            self.scan(explicit=True)
            self.app.deiconify()
        self.app.after(450,capture_and_restore)

    def import_map(self):
        path = filedialog.askopenfilename(filetypes=[(tr('Map screenshot'),'*.png *.jpg *.jpeg *.webp')])
        if path:
            with Image.open(path) as im:
                self.last_image = im.convert('RGB')
            self.last_reading = self.detector.detect(self.last_image)
            if len(self.last_reading.get('candidates',[]))==1:
                self.accept_layout(self.last_reading['candidates'][0],self.last_reading)
            self.paint()
            self.status.set(self.last_reading.get('reason','Screenshot loaded.'))

    def paint(self):
        if self.engine and hasattr(self,'preview'):
            image=self.engine.render((max(100,self.preview.winfo_width()),max(100,self.preview.winfo_height())),int(self.keys.get()),None,self.player,1.,False,time.monotonic()-self.position_time<2,**self.render_options())
            self.photo=ImageTk.PhotoImage(image);self.preview.delete('all');self.preview.create_image(0,0,image=self.photo,anchor='nw')
            self.route_status.set(f'{self.difficulty.get()} · layout {self.engine.layout} · Orange solid / Blue dashed: routes from each entrance. Egg icons: possible nests. Trials: known positions'+(' + unconfirmed (?)' if self.unconfirmed_trials.get() else '')+'.')
            return
        if self.last_image is None or not self.preview.winfo_exists():
            if self.preview.winfo_exists():
                self.preview.delete('all')
                width,height=max(100,self.preview.winfo_width()),max(100,self.preview.winfo_height())
                self.preview.create_text(width/2,height/2,text=tr('Open the game map to begin\nOr choose a layout to explore routes'),width=width-30,fill='#8c9db5',font=('Segoe UI',13),justify='center',tags='empty')
            return
        image = self.last_image.copy()
        image.thumbnail((max(100,self.preview.winfo_width()),max(100,self.preview.winfo_height())))
        self.photo = ImageTk.PhotoImage(image)
        self.preview.delete('all')
        self.preview.create_image(0,0,image=self.photo,anchor='nw')
        scale = image.width/self.last_image.width
        for kind,color in [('orange','#ffae50'),('blue','#4bc7ff'),('player','#68e1b9')]:
            if kind in self.last_reading:
                x,y = [n*scale for n in self.last_reading[kind]]
                self.preview.create_oval(x-9,y-9,x+9,y+9,outline=color,width=2)
                self.preview.create_text(x+12,y,text=tr(kind),fill=color,anchor='w')

    def inspect_room(self,event):
        if not self.engine:return
        engine=self.engine;w,h=self.preview.winfo_width(),self.preview.winfo_height()
        scale=min(w/engine.image.width,h/engine.image.height)
        ox,oy=(w-engine.image.width*scale)/2,(h-engine.image.height*scale)/2
        closest=None
        for group,label in [('keyrooms','Key doors'),('nests','Egg nests'),('challenges','Sanctums / trials'),('rooms','Chest rooms'),('mobs','Monsters')]:
            for room in (engine.treasure_rooms if group=='rooms' else engine.data.get(group,[])):
                x=ox+room['x']/100*engine.image.width*scale;y=oy+room['y']/100*engine.image.height*scale
                distance=((event.x-x)**2+(event.y-y)**2)**.5
                if distance<=24 and (closest is None or distance<closest[0]):closest=(distance,group,label,room)
        if closest is None:
            self.room_details.set('Click a room icon for details.');return
        _,group,label,room=closest
        details=[tr(label)]
        if group=='keyrooms':
            if 'nest' in room:details.append(tr('Egg chance: ')+f"{room['nest']:.0%}")
            details.append(tr('Chest variants: ')+str(len(room.get('variants',[]))))
        elif group=='rooms':
            details.extend(tr(name)+': '+str(room.get(key,0)) for name,key in [('Gold','gold'),('Purple','purple'),('Blue','blue')])
            if room.get('top'):details.append(tr('Check upstairs'))
        elif group=='mobs':details.append(tr('Possible enemies: ')+str(room.get('max',0)))
        elif room.get('maybe'):details.append(tr('Unconfirmed position'))
        else:details.append(tr('Possible spawn location'))
        self.room_details.set(' · '.join(details))

    def calibrate(self):
        if self.last_image is None:
            path = self.folder/'last-map.png'
            if path.exists():
                with Image.open(path) as im:
                    self.last_image = im.convert('RGB')
            else:
                messagebox.showinfo(tr('Calibrate'),tr('Open M in the game and Capture open M map, or import a screenshot first.'))
                return
        image = self.last_image.copy()
        shown = image.copy()
        shown.thumbnail((min(1400,self.app.winfo_screenwidth()-80),self.app.winfo_screenheight()-180))
        scale = shown.width/image.width
        window = tk.Toplevel(self.app)
        window.title('Click orange portal, blue portal, then optionally your player marker')
        step = tk.StringVar(value='1. Click the CENTER of the orange entrance icon on the game map.')
        ttk.Label(window,textvariable=step,padding=10).pack(anchor='w')
        canvas = tk.Canvas(window,width=shown.width,height=shown.height,highlightthickness=0)
        canvas.pack()
        canvas.photo = ImageTk.PhotoImage(shown)
        canvas.create_image(0,0,image=canvas.photo,anchor='nw')
        points = []
        def click(event):
            if len(points)>=3:
                return
            points.append((round(event.x/scale),round(event.y/scale)))
            canvas.create_oval(event.x-10,event.y-10,event.x+10,event.y+10,outline=('orange','cyan','#68e1b9')[len(points)-1],width=3)
            step.set(('2. Click the CENTER of the blue entrance icon.','3. Optionally click YOUR player marker; then Save.','Ready. Choose the known layout below, if you know it, then Save.')[len(points)-1])
        canvas.bind('<Button-1>',click)
        bar = ttk.Frame(window,padding=10)
        bar.pack(fill='x')
        ttk.Label(bar,text='Known layout (optional):').pack(side='left')
        known = ttk.Combobox(bar,state='readonly',values=['Unknown']+[str(x) for x in layouts_for(self.difficulty.get())],width=12)
        known.current(0)
        known.pack(side='left',padx=8)
        def save():
            if len(points)<2:
                step.set('Select both portal centers first.')
                return
            try:
                layout = int(known.get()) if known.get()!='Unknown' else None
                self.detector.calibrate(image,points[0],points[1],points[2] if len(points)>2 else None,layout)
                self.last_reading = self.detector.detect(image)
                self.paint()
                self.status.set('Calibrated from your screen. Open M during a run to identify and update the map.')
                window.destroy()
            except Exception as exc:
                step.set(str(exc))
        ttk.Button(bar,text='Save calibration',command=save).pack(side='left')

    def select_layout(self):
        if self.layout.get()=='Auto / waiting':
            self.manual_layout = None
            self.session.map_confirmed=False
            self.map_open=False;self.map_rescan_pending=False
            self.generation+=1
            self.scan_until=0;self.next_screen_probe=0;self.position_time=0
            self.last_reading={};self.last_image=None
            self.config.update(layout=None,player=None,reading={},map_confirmed=False)
            self.engine=None;self.player=None;self.overlay.hide();self.overlay_dirty=True
            self.status.set('Waiting for map · open '+self.app.shortcut_hint('map'))
            self.paint()
        else:
            self.manual_layout = int(self.layout.get())
            self.config['layout'] = self.manual_layout
            self.accept_layout(self.manual_layout,self.last_reading)
            if not self.session.map_confirmed:
                self.status.set(f'Preview layout {self.manual_layout} · not detected. Open the full game map to confirm tracking.')
            if self.last_image is not None and all(k in self.last_reading for k in ('orange','blue')):
                self.detector.calibrate(self.last_image,self.last_reading['orange'],self.last_reading['blue'],
                    layout=self.manual_layout)
                self.config['reading'] = {k:self.last_reading[k] for k in ('orange','blue','player') if k in self.last_reading}
        self.write_config()

    def open_simulator(self):
        if not (ASSETS/'simulator'/'index.html').exists():
            webbrowser.open(SITE_URL)
            self.route_status.set('Opening AniimoTools in your browser. The native map preview and overlay remain local.')
            return
        self.save_preferences()
        self.config['shutdown'] = False
        (self.folder/'viewer-error.txt').unlink(missing_ok=True)
        self.write_config()
        if self.process is not None and self.process.poll() is None:
            self.route_status.set('The two companion windows are already open; layout changes update them automatically.')
            return
        args = [sys.executable,'--sanctum-view',str(self.config_path)] if getattr(sys,'frozen',False) else [sys.executable,str(Path(__file__).with_name('app.py')),'--sanctum-view',str(self.config_path)]
        self.process = subprocess.Popen(args,creationflags=subprocess.CREATE_NO_WINDOW)
        self.route_status.set('Opening local simulator · orange and blue entrance routes · works offline')

    def close(self):
        for timer in (self.adjust_render_id,self.adjust_save_id):
            if timer is not None:self.app.after_cancel(timer)
        if self.adjust_save_id is not None:self.save_preferences()
        self.config['shutdown'] = True
        self.write_config()
        self.overlay.close()

    def accept_layout(self,layout,reading):
        if not self.assets_ready:
            self.status.set('Download the map pack in Map & routes first.');return
        if layout in reading.get('candidates',[]) and 'orange' in reading and 'blue' in reading:
            self.session.confirm_map()
            self.session.inside_dungeon=True
            self.outdoors=False;self.outdoor_votes=0
            self.map_feedback=f'{self.difficulty.get()} {layout} · Map confirmed'
        elif reading.get('kind')=='match' and reading.get('method')=='temporal-corridors' and reading.get('layout')==layout:
            self.session.confirm_map()
            self.session.inside_dungeon=True
            self.outdoors=False;self.outdoor_votes=0
        changed=not self.engine or self.engine.layout!=layout
        if changed:self.engine=self.maps.model(layout)
        self.layout.set(str(layout));self.config['layout']=layout
        position=self.engine.position_from_map(reading)
        if reading.get('reference_position') is not None:position=self.engine.position_from_reference(reading['reference_position'])
        if position:
            self.player=position;self.position_time=0
        self.remember_evidence(layout,reading)
        self.config.update(player=self.player,map_confirmed=self.session.map_confirmed,reading={k:reading[k] for k in ('orange','blue','player') if k in reading})
        self.overlay_dirty=True;self.paint();self.write_config()

    def remember_evidence(self,layout,reading):
        score=evidence_score(reading,layout)
        if not score:return
        if score>=evidence_score(self.last_reading,layout):self.last_reading=dict(reading)
        if hasattr(self.app,'party'):self.app.party.observed_layout(layout,self.last_reading)

    def set_minimap(self):
        self.app.withdraw();self.overlay.hide()
        def capture():
            settings=self.app.ledger.settings()
            try:
                self.capture_geometry()
                image=capture_image(settings['monitor'],settings.get('capture_target','auto')).convert('RGB')
            except (OSError,ValueError) as exc:
                self.app.deiconify();self.status.set(str(exc));return
            self.app.deiconify();window=tk.Toplevel(self.app);window.title('Drag tightly around the minimap; release to save')
            shown=image.copy();shown.thumbnail((1200,750))
            canvas=tk.Canvas(window,width=shown.width,height=shown.height,highlightthickness=0);canvas.pack()
            canvas.photo=ImageTk.PhotoImage(shown);canvas.create_image(0,0,image=canvas.photo,anchor='nw')
            start=[]
            def press(e):start[:]=[e.x,e.y];canvas.delete('box')
            def drag(e):
                if start:canvas.delete('box');canvas.create_rectangle(*start,e.x,e.y,outline='#68e1b9',width=2,tags='box')
            def release(e):
                if not start:return
                x0,x1=sorted((start[0],e.x));y0,y1=sorted((start[1],e.y))
                if x1-x0<40 or y1-y0<40:return
                self.config['minimap_region']=[x0/shown.width,y0/shown.height,x1/shown.width,y1/shown.height]
                self.write_config();self.generation+=1;window.destroy();self.status.set('Minimap area saved; tracking resumes in Aniimo.')
            canvas.bind('<Button-1>',press);canvas.bind('<B1-Motion>',drag);canvas.bind('<ButtonRelease-1>',release)
        self.app.after(450,capture)
