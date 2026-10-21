"""Aniimo Eggheist Tracker: a local Windows desktop companion."""
import csv
import ctypes
import json
import math
import os
import queue
import re
import shutil
import sys
if __name__=='__main__' and sys.argv[1:2]==['--apply-update']:
    from update_install import run_helper
    sys.exit(run_helper(sys.argv[2:]))
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from PIL import Image, ImageTk
from tracker_core import Ledger, forecast, PRICES, ticket_cost, break_even
from windows_capture import Hotkeys, capture, monitors, recognize,game_windows
from readings import DEFAULT_REGIONS, parse_amount, single_amount, parse_points, single_points, loot_reading, rank_points_reading, lifetime_reading
from sanctum_panel import SanctumPanel
from screen_kind import screen_kind
from map_engine import MapLibrary
from shortcut_keys import DEFAULT_SHORTCUTS, LABELS, GLOBAL_ACTIONS, ACTION_IDS, compile_shortcuts
from analytics_panel import AnalyticsPanel
from i18n import Localizer,LANGUAGES,set_language as activate_language,tr
from pt_br import HELP_PT_BR
from screenshot_retention import prune_screenshots
from party_panel import PartyPanel
from tutorial import Tutorial
from update_checker import UpdatesPanel
from budget_panel import BudgetPanel

BG = '#0d1421'
PANEL = '#182235'
TEXT = '#edf5f5'
MUTED = '#98aac3'
ACCENT = '#79dcc8'


class App(tk.Tk):
    def __init__(self, data_dir=None, hotkeys=True):
        super().__init__()
        self.title('Aniimo · Eggheist Tracker')
        from asset_paths import BUNDLED
        self.iconbitmap(default=str(BUNDLED/'branding/app.ico'))
        self.geometry(f'{min(1320,self.winfo_screenwidth()-60)}x{min(920,self.winfo_screenheight()-90)}')
        self.minsize(1000,640)
        self.configure(bg=BG)
        self.data_dir = Path(data_dir or Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'AniimoTracker')
        self.data_dir.mkdir(parents=True, exist_ok=True)
        (self.data_dir / 'screenshots').mkdir(exist_ok=True)
        self.ledger = Ledger(self.data_dir / 'tracker.db')
        capture_settings=self.ledger.settings()
        capture_space='monitor' if capture_settings['capture_target']=='monitor' else 'client'
        if capture_settings.get('regions_space','monitor')!=capture_space:
            self.ledger.configure(regions={},regions_space=capture_space)
        language=self.ledger.settings().get('language','en')
        self.localizer=Localizer(self,language if language in LANGUAGES else 'en')
        self.next_locale_refresh=0
        self.messages = queue.Queue()
        self.auto_messages=queue.Queue()
        self.auto_busy=False
        self.auto_pending=[]
        self.auto_maps=MapLibrary()
        self.hotkeys_enabled=hotkeys
        self.shortcuts_path=self.data_dir/'shortcuts.json'
        try:
            self.shortcuts={**DEFAULT_SHORTCUTS,**json.loads(self.shortcuts_path.read_text(encoding='utf-8'))}
            self.shortcut_specs=compile_shortcuts(self.shortcuts)
        except (OSError,ValueError,TypeError,AttributeError):
            self.shortcuts=dict(DEFAULT_SHORTCUTS)
            self.shortcut_specs=compile_shortcuts(self.shortcuts)
        self.hk = Hotkeys(self.shortcut_specs) if hotkeys else None
        self.generations = {'money': 0, 'points': 0, 'balance': 0}
        self.balance_approximate = False
        self.status = tk.StringVar(value='Ready · screenshots and OCR stay on this PC')
        self.draft_images = {}
        self.busy_capture = False
        self.pending_ocr=set()
        self.screenshot_cleanup_due=True
        self.next_screenshot_cleanup=0
        self.fields = {}
        self.style()
        self.tutorial=Tutorial(self)
        self.header()
        self.workspace=ttk.Frame(self);self.workspace.pack(fill='both',expand=True)
        self.navigation=ttk.Frame(self.workspace,style='Sidebar.TFrame',padding=(12,20));self.navigation.pack(side='left',fill='y')
        self.navigation.configure(width=166);self.navigation.pack_propagate(False)
        self.tabs = ttk.Notebook(self.workspace,style='Workspace.TNotebook')
        self.tabs.pack(side='left',fill='both', expand=True, padx=18, pady=(4, 8))
        self.home, self.history, self.settings_tab, self.help_tab = [ttk.Frame(self.tabs, padding=18) for _ in range(4)]
        for tab, title in zip((self.home, self.history, self.settings_tab, self.help_tab),
                              ('  Dashboard & new run  ', '  Run history  ', '  Settings  ', '  How it works  ')):
            self.tabs.add(tab, text=title)
        home_shell = self.home
        home_canvas = tk.Canvas(home_shell, bg=BG, highlightthickness=0)
        home_scroll = ttk.Scrollbar(home_shell, orient='vertical', command=home_canvas.yview)
        home_canvas.configure(yscrollcommand=home_scroll.set)
        home_scroll.pack(side='right', fill='y')
        home_canvas.pack(side='left', fill='both', expand=True)
        self.home = ttk.Frame(home_canvas)
        home_window = home_canvas.create_window(0, 0, window=self.home, anchor='nw')
        self.home.bind('<Configure>', lambda event: home_canvas.configure(scrollregion=home_canvas.bbox('all')))
        home_canvas.bind('<Configure>', lambda event: home_canvas.itemconfigure(home_window, width=event.width))
        self.enable_wheel_scroll(home_canvas,self.home)
        settings_shell=self.settings_tab
        settings_canvas=tk.Canvas(settings_shell,bg=BG,highlightthickness=0)
        settings_scroll=ttk.Scrollbar(settings_shell,orient='vertical',command=settings_canvas.yview)
        settings_canvas.configure(yscrollcommand=settings_scroll.set)
        settings_scroll.pack(side='right',fill='y');settings_canvas.pack(side='left',fill='both',expand=True)
        self.settings_tab=ttk.Frame(settings_canvas)
        settings_window=settings_canvas.create_window(0,0,window=self.settings_tab,anchor='nw')
        self.settings_tab.bind('<Configure>',lambda event:settings_canvas.configure(scrollregion=settings_canvas.bbox('all')))
        settings_canvas.bind('<Configure>',lambda event:settings_canvas.itemconfigure(settings_window,width=event.width))
        self.enable_wheel_scroll(settings_canvas,self.settings_tab)
        self.dashboard()
        self.build_history()
        self.build_settings()
        self.build_help()
        self.sanctum_tab = ttk.Frame(self.tabs,padding=18)
        self.tabs.insert(1,self.sanctum_tab,text='  Map  ')
        self.sanctum = SanctumPanel(self,self.sanctum_tab)
        self.analytics_tab=ttk.Frame(self.tabs,padding=18)
        self.tabs.insert(3,self.analytics_tab,text='  Analytics  ')
        self.analytics=AnalyticsPanel(self,self.analytics_tab)
        self.party_tab=ttk.Frame(self.tabs,padding=18)
        self.tabs.insert(4,self.party_tab,text='  Party  ')
        self.party=PartyPanel(self,self.party_tab)
        self.build_navigation()
        ttk.Label(self, textvariable=self.status, foreground=MUTED).pack(anchor='w', padx=28, pady=(0, 12))
        self.restore_draft()
        self.cleanup_screenshots()
        self.refresh()
        self.localizer.refresh(self)
        self.localizer.refresh()
        if self.sanctum.session.standalone:self.tabs.select(1)
        self.protocol('WM_DELETE_WINDOW', self.close)
        self.tick_id = self.after(100, self.tick)
        self.map_input_tick_id = self.after(16, self.poll_map_input)
        if hotkeys:self.after(900,self.tutorial.first_use)
        if self.hk and self.hk.failed:
            self.status.set('Some shortcuts are already in use. Capture buttons and image import still work.')

    def style(self):
        s = ttk.Style(self)
        s.theme_use('clam')
        s.configure('.', background=BG, foreground=TEXT, font=('Segoe UI', 10))
        s.configure('TFrame', background=BG)
        s.configure('Panel.TFrame', background=PANEL)
        s.configure('TLabel', background=BG, foreground=TEXT)
        s.configure('Muted.TLabel', foreground=MUTED)
        s.configure('Title.TLabel', font=('Segoe UI Semibold', 25))
        s.configure('Big.TLabel', font=('Segoe UI Semibold', 23), foreground=ACCENT, background=PANEL)
        s.configure('Panel.TLabel', background=PANEL)
        s.configure('TButton', background='#284350', padding=(12, 8), borderwidth=0)
        s.map('TButton', background=[('active', '#355c6a')])
        s.configure('Accent.TButton', foreground=BG, background=ACCENT)
        s.map('Accent.TButton', background=[('active', '#9cf0d3')])
        s.configure('TEntry', fieldbackground='#233b48', foreground=TEXT, insertcolor=TEXT, padding=5)
        s.configure('TCombobox', fieldbackground='#233b48', foreground=TEXT, padding=5)
        s.map('TCombobox', fieldbackground=[('readonly', '#233b48')], selectbackground=[('readonly', '#233b48')])
        s.configure('TNotebook', background=BG, borderwidth=0)
        s.configure('TNotebook',bordercolor=BG,lightcolor=BG,darkcolor=BG)
        s.configure('Horizontal.TScale',background='#79dcc8',troughcolor='#263a53',bordercolor=PANEL,lightcolor=PANEL,darkcolor=PANEL)
        s.configure('TNotebook.Tab', background=PANEL, padding=(12, 10))
        s.map('TNotebook.Tab', background=[('selected', '#31515e')])
        s.configure('Treeview', background=PANEL, fieldbackground=PANEL, foreground=TEXT, rowheight=30)
        s.configure('Panel.TCheckbutton', background=PANEL, foreground=TEXT)
        s.map('Panel.TCheckbutton', background=[('active', PANEL)])
        s.configure('Card.TButton', font=('Segoe UI', 9), padding=(6, 4), width=0)
        s.configure('Treeview.Heading', background='#284350', foreground=TEXT, padding=7)
        s.map('Treeview', background=[('selected', '#355c6a')])
        s.configure('TCheckbutton', background=BG, foreground=TEXT)
        s.configure('Sidebar.TFrame',background='#101a2b')
        s.configure('Sidebar.TLabel',background='#101a2b',foreground=MUTED)
        s.configure('Nav.TButton',background='#101a2b',foreground=MUTED,anchor='w',padding=(14,13),borderwidth=0)
        s.map('Nav.TButton',background=[('active','#22334b')],foreground=[('active',TEXT)])
        s.configure('NavActive.TButton',background='#263d51',foreground='#a4f4df',anchor='w',padding=(14,13),borderwidth=0)
        s.configure('Workspace.TNotebook',background=BG,borderwidth=0)
        s.layout('Workspace.TNotebook.Tab',[])
        s.configure('Panel.TRadiobutton',background=PANEL,foreground=TEXT,padding=(0,2))
        s.configure('Panel.TCheckbutton',background=PANEL,foreground=TEXT,padding=(0,2))
        s.map('Panel.TCheckbutton',background=[('active',PANEL)])
        s.configure('Chip.TRadiobutton',background='#22334b',foreground=TEXT,padding=(9,8),indicatorrelief='flat')
        s.map('Chip.TRadiobutton',background=[('selected','#385770'),('active','#2e4660')])
        s.configure('TSpinbox',fieldbackground='#23344c',foreground=TEXT,padding=6)
        s.configure('Workspace.TNotebook',bordercolor=BG,lightcolor=BG,darkcolor=BG)
        s.configure('Goal.Horizontal.TProgressbar', background=ACCENT, troughcolor='#263a53',
                    borderwidth=0, lightcolor=ACCENT, darkcolor=ACCENT,bordercolor=PANEL,thickness=6)
        s.layout('Goal.Horizontal.TProgressbar',[
            ('Horizontal.Progressbar.trough',{'sticky':'nswe','children':[
                ('Horizontal.Progressbar.pbar',{'side':'left','sticky':'ns'})]})])
        s.configure('TButton',background='#24364c')
        s.map('TButton',background=[('active','#314a68')])
        for name in ('TEntry','TCombobox','TSpinbox'):
            s.configure(name,bordercolor='#344962',lightcolor='#344962',darkcolor='#344962',arrowcolor=MUTED)
        for name in ('TCheckbutton','Panel.TCheckbutton','Panel.TRadiobutton','Chip.TRadiobutton'):
            s.configure(name,indicatorbackground='#263a53',indicatorforeground=ACCENT,upperbordercolor='#4b607a',lowerbordercolor='#4b607a')
        s.configure('Vertical.TScrollbar',background='#293c55',troughcolor=BG,bordercolor=BG,lightcolor=BG,darkcolor=BG,arrowcolor=MUTED,arrowsize=12)
        s.map('Vertical.TScrollbar',background=[('disabled',PANEL)],troughcolor=[('disabled',BG)])


    def enable_wheel_scroll(self,canvas,content):
        def scroll(event):
            widget=event.widget
            if getattr(widget,'winfo_class',lambda:'' )()=='TSpinbox':return
            while widget is not None:
                if widget is content or widget is canvas:
                    canvas.yview_scroll(-int(event.delta/120),'units')
                    return 'break'
                widget=getattr(widget,'master',None)
        self.bind_all('<MouseWheel>',scroll,add=True)

    def build_navigation(self):
        ttk.Label(self.navigation,text='WORKSPACE',style='Sidebar.TLabel',font=('Segoe UI Semibold',9)).pack(anchor='w',padx=14,pady=(0,18))
        self.navigation_buttons=[]
        for index,title in enumerate(('Overview','Map & routes','Run history','Analytics','Party','Settings','Help')):
            button=ttk.Button(self.navigation,text=title,style='Nav.TButton',command=lambda i=index:self.tabs.select(i))
            button.pack(fill='x',pady=3);self.navigation_buttons.append(button)
        self.nav_hint=tk.StringVar(value=f'CAPTURE\n{self.shortcut_hint("capture")}\n\nOVERLAY\n{self.shortcut_hint("overlay")}')
        ttk.Label(self.navigation,textvariable=self.nav_hint,style='Sidebar.TLabel',font=('Segoe UI',9),justify='left').pack(side='bottom',anchor='w',padx=14,pady=18)
        self.tabs.bind('<<NotebookTabChanged>>',lambda e:self.update_navigation())
        self.update_navigation()

    def update_navigation(self):
        selected=self.tabs.index(self.tabs.select())
        for index,button in enumerate(self.navigation_buttons):button.configure(style='NavActive.TButton' if index==selected else 'Nav.TButton')

    def header(self):
        header = ttk.Frame(self, padding=(28, 20, 28, 12))
        header.pack(fill='x')
        ttk.Button(header,text='?',width=3,command=self.tutorial.open).pack(side='right',anchor='n')
        ttk.Label(header, text='ANIIMO  /  EGGHEIST COMPANION', foreground=ACCENT,
                  font=('Segoe UI Semibold', 10)).pack(anchor='w')
        self.run_heading=tk.StringVar(value='Between runs')
        self.run_guidance=tk.StringVar(value='Open Inventory after shopping, then capture with Ctrl+Shift+F8 to start.')
        ttk.Label(header, textvariable=self.run_heading, style='Title.TLabel').pack(anchor='w', pady=(3, 2))
        guidance=ttk.Label(header, textvariable=self.run_guidance, style='Muted.TLabel')
        guidance.pack(anchor='w')
        self.party_notice=tk.StringVar(value='')
        self.party_notice_frame=ttk.Frame(header)
        ttk.Label(self.party_notice_frame,textvariable=self.party_notice,foreground='#ffd083',wraplength=1000).pack(side='left')
        ttk.Button(self.party_notice_frame,text='×',width=3,command=lambda:self.set_party_notice('')).pack(side='right')
        self.update_notice=tk.StringVar()
        self.update_notice_frame=ttk.Frame(header,style='Panel.TFrame',padding=(12,6))
        ttk.Label(self.update_notice_frame,textvariable=self.update_notice,style='Panel.TLabel').pack(side='left')
        self.update_action=ttk.Button(self.update_notice_frame,text='Update & restart',command=lambda:self.updates.install_update())
        self.update_action.pack(side='right',padx=(12,0))
        header.bind('<Configure>',lambda event:guidance.configure(wraplength=max(300,event.width-56)))

    def set_party_notice(self,text):
        self.party_notice.set(text)
        if text:self.party_notice_frame.pack(fill='x',pady=(8,0))
        else:self.party_notice_frame.pack_forget()

    def dashboard(self):
        def wrap_labels(event):
            width=max(260,event.width-4)
            for label in self.home.winfo_children():
                if isinstance(label,ttk.Label) and int(label.cget('wraplength') or 0)>0 and int(label.cget('wraplength'))!=width:
                    label.configure(wraplength=width)
        self.home.bind('<Configure>',wrap_labels,add='+')
        self.capture_labels = {}
        cards = ttk.Frame(self.home)
        cards.pack(fill='x')
        self.card_values = {}
        self.stat_cards = []
        for i, (key, title) in enumerate((('rank', 'TOTAL POINTS'), ('tickets', 'TICKETS ON HAND'),
                                         ('today', 'TODAY’S POINTS'), ('net', 'COIN BALANCE'))):
            cards.columnconfigure(i, weight=1, uniform='cards')
            card = ttk.Frame(cards, style='Panel.TFrame', padding=14)
            card.grid(row=0, column=i, sticky='nsew', padx=(0 if i == 0 else 8, 0))
            self.stat_cards.append(card)
            ttk.Label(card, text=title, style='Panel.TLabel', foreground=MUTED,
                      font=('Segoe UI', 9)).pack(anchor='w')
            var = tk.StringVar()
            self.card_values[key] = var
            ttk.Label(card, textvariable=var, style='Big.TLabel').pack(anchor='w', pady=(5, 0))
            if key == 'tickets':
                actions = ttk.Frame(card, style='Panel.TFrame')
                actions.pack(anchor='w', pady=(8, 0))
                self.buy_tickets_button = ttk.Button(actions, text='Buy tickets', style='Card.TButton', command=self.buy_dialog)
                self.buy_tickets_button.pack(side='left', padx=(0, 5))
                self.free_tickets_button = ttk.Button(actions, text='Free tickets', style='Card.TButton', command=self.ticket_reward_dialog)
                self.free_tickets_button.pack(side='left')
            elif key == 'rank':
                self.progress_caption=tk.StringVar()
                caption=ttk.Label(card,textvariable=self.progress_caption,style='Panel.TLabel',foreground=MUTED,font=('Segoe UI',9),wraplength=220)
                caption.pack(anchor='w',pady=(4,0))
                card.bind('<Configure>',lambda event:caption.configure(wraplength=max(100,event.width-28)))
                ttk.Button(card, text='Correct stats', style='Card.TButton', command=self.correct_stats_dialog).pack(anchor='w', pady=(8, 0))
            elif key == 'net':
                self.balance_source_text=tk.StringVar()
                ttk.Label(card,textvariable=self.balance_source_text,style='Panel.TLabel',
                          foreground=MUTED,font=('Segoe UI',9)).pack(anchor='w',pady=(8,0))
        def arrange_cards(event):
            columns = 2 if event.width < 800 else 4
            for column in range(4):
                cards.columnconfigure(column, weight=1 if column < columns else 0,
                                      uniform='cards' if column < columns else '')
            for index, card in enumerate(self.stat_cards):
                row, column = divmod(index, columns)
                card.grid(row=row, column=column, padx=(0 if column == 0 else 8, 0),
                          pady=(0 if row == 0 else 8, 0))
        cards.bind('<Configure>', arrange_cards)
        self.forecast_text = tk.StringVar()
        self.goal_summary=ttk.Frame(self.home,style='Panel.TFrame',padding=(14,12))
        self.goal_summary.pack(fill='x',pady=(12,14))
        ttk.Label(self.goal_summary,text='GOAL ESTIMATE',style='Panel.TLabel',foreground=MUTED,
                  font=('Segoe UI Semibold',9)).pack(anchor='w',pady=(0,5))
        ttk.Label(self.goal_summary, textvariable=self.forecast_text, foreground=ACCENT,
                  style='Panel.TLabel',font=('Segoe UI Semibold', 11), wraplength=900).pack(anchor='w')
        self.goal_progress_text=tk.StringVar()
        ttk.Label(self.goal_summary,textvariable=self.goal_progress_text,style='Panel.TLabel',foreground=MUTED,font=('Segoe UI',9)).pack(anchor='w',pady=(7,3))
        self.goal_progress=ttk.Progressbar(self.goal_summary,style='Goal.Horizontal.TProgressbar',maximum=100)
        self.goal_progress.pack(fill='x',pady=(0,9))
        self.playtime_text = tk.StringVar()
        self.goal_time_label=ttk.Label(self.goal_summary, textvariable=self.playtime_text,
                  style='Panel.TLabel',wraplength=900)
        self.goal_time_label.pack(anchor='w')
        self.goal_details=self.disclosure(self.goal_summary,'Estimate details')
        self.goal_details.configure(style='Panel.TFrame')
        self.goal_details_text=tk.StringVar()
        self.goal_details_label=ttk.Label(self.goal_details,textvariable=self.goal_details_text,
                  style='Panel.TLabel',foreground=MUTED,wraplength=700,justify='left')
        self.goal_details_label.pack(anchor='w')
        self.goal_details.bind('<Configure>',lambda event:self.goal_details_label.configure(wraplength=max(240,event.width)))
        self.goal_summary.bind('<Configure>',lambda event:[child.configure(wraplength=max(260,event.width-28))
            for child in self.goal_summary.winfo_children() if isinstance(child,ttk.Label)])
        self.budget_text = tk.StringVar()
        start_actions=ttk.Frame(self.home);start_actions.pack(fill='x')
        self.capture_button=ttk.Button(start_actions,text=f'Capture screen · {self.shortcut_hint("capture")}',style='Accent.TButton',command=lambda:self.capture_image('auto',from_button=True))
        self.capture_button.pack(side='left')
        self.fields['balance']=tk.StringVar()
        self.fields['balance'].trace_add('write',lambda *args:setattr(self,'balance_approximate',False))
        ttk.Label(start_actions,text='Balance (optional)',style='Muted.TLabel').pack(side='left',padx=(16,5))
        self.start_balance_entry=ttk.Entry(start_actions,textvariable=self.fields['balance'],width=15)
        self.start_balance_entry.pack(side='left')
        self.manual_start_button=ttk.Button(start_actions,text='Start run',command=lambda:self.begin_run(manual=True))
        self.manual_start_button.pack(side='left',padx=10)
        self.run_info=tk.StringVar()
        self.capture_labels['balance']=self.run_info
        ttk.Label(self.home,textvariable=self.run_info,style='Muted.TLabel',wraplength=980).pack(anchor='w',pady=(8,14))
        ttk.Separator(self.home).pack(fill='x',pady=(0,12))
        ttk.Label(self.home,text='Record a run',font=('Segoe UI Semibold',17)).pack(anchor='w')
        ttk.Label(self.home,text='Capture the result or enter it below. Points are required; loot value is optional.',style='Muted.TLabel',wraplength=980).pack(anchor='w',pady=(4,10))
        values=ttk.Frame(self.home);values.pack(fill='x')
        self.failed_run = tk.BooleanVar(value=False)
        for col,(kind,label) in enumerate((('money','Loot value (optional)'),('points','Points gained / lost'))):
            values.columnconfigure(col,weight=1)
            box=ttk.Frame(values,style='Panel.TFrame',padding=12)
            box.grid(row=0,column=col,sticky='nsew',padx=(0 if col==0 else 8,0))
            ttk.Label(box,text=label,style='Panel.TLabel').pack(anchor='w')
            self.fields[kind]=tk.StringVar()
            ttk.Entry(box,textvariable=self.fields[kind]).pack(fill='x',pady=6)
            self.capture_labels[kind]=tk.StringVar(value='Type a value or capture a screenshot')
            ttk.Label(box,textvariable=self.capture_labels[kind],style='Panel.TLabel',foreground=MUTED).pack(anchor='w')
            if kind == 'points':
                self.failed_run_check = ttk.Checkbutton(box, text='Failed run · enter points lost (e.g. 140)', variable=self.failed_run, style='Panel.TCheckbutton')
                self.failed_run_check.pack(anchor='w', pady=(6, 0))
        self.save_run_button=ttk.Button(self.home,text='Save run',style='Accent.TButton',command=self.save_run)
        self.save_run_button.pack(anchor='w',pady=(14,8))
        ttk.Label(self.home,text='Loot value is tracked separately from your actual coin balance.',style='Muted.TLabel').pack(anchor='w',pady=(0,10))
        self.budget_panel=BudgetPanel(self.home,self.open_budget_settings)
        self.budget_panel.pack(fill='x',pady=(6,12))
        self.more_options=self.disclosure(self.home,'More options')
        options=self.more_options
        maintenance=ttk.Frame(options);maintenance.pack(fill='x',pady=8)
        ttk.Button(maintenance,text='Cancel mistaken run start',command=self.cancel_run_start).pack(side='left')
        spending=ttk.Frame(options);spending.pack(fill='x',pady=8)
        ttk.Label(spending,text='Spending (optional)').pack(side='left')
        self.spend_amount=tk.StringVar();self.spend_note=tk.StringVar()
        ttk.Entry(spending,textvariable=self.spend_amount,width=14).pack(side='left',padx=8)
        ttk.Entry(spending,textvariable=self.spend_note,width=18).pack(side='left')
        ttk.Button(spending,text='Log spending',command=self.log_spending).pack(side='left',padx=8)
        self.fields['lifetime']=tk.StringVar()
        ttk.Label(options,text='Lifetime points after run (optional)').pack(anchor='w')
        ttk.Entry(options,textvariable=self.fields['lifetime'],width=22).pack(anchor='w',pady=4)
        flags=ttk.Frame(options);flags.pack(fill='x',pady=8)
        self.consumes=tk.BooleanVar(value=True);self.already_included=tk.BooleanVar(value=False)
        ttk.Checkbutton(flags,text='Uses 1 Chaos ticket',variable=self.consumes).pack(side='left')
        ttk.Checkbutton(flags,text='Already included in current stats',variable=self.already_included).pack(side='left',padx=8)
        self.run_day=tk.StringVar(value=str(self.ledger.game_day()))
        ttk.Entry(flags,textvariable=self.run_day,width=12).pack(side='left')
        self.notes=tk.StringVar();ttk.Label(options,text='Optional note').pack(anchor='w')
        ttk.Entry(options,textvariable=self.notes).pack(fill='x',pady=4)
        for kind in ('balance','money','points'):
            tools=ttk.Frame(options);tools.pack(fill='x',pady=4)
            ttk.Label(tools,text={'balance':'Inventory','money':'Loot','points':'Points'}[kind],width=12).pack(side='left')
            for label,action in [('Import image',lambda k=kind:self.import_image(k)),('View image',lambda k=kind:self.view_image(k)),('Reading area',lambda k=kind:self.choose_region(k))]:
                ttk.Button(tools,text=label,command=action).pack(side='left',padx=4)
        ttk.Button(options,text='Clear result draft',command=self.clear_draft).pack(side='left',pady=8)
        ttk.Button(options,text='Show OCR text',command=self.show_ocr).pack(side='left',padx=8,pady=8)

    def open_budget_settings(self):
        self.settings_section.set('Goals & budget')
        self.show_settings_section()
        self.tabs.select(self.settings_tab.master.master)

    def disclosure(self,parent,title):
        button=ttk.Button(parent,text=title+' ▸')
        button.pack(anchor='w',pady=5)
        body=ttk.Frame(parent)
        def show():
            body.pack(after=button,fill='x',pady=(0,8));button.configure(text=title+' ▾')
        def toggle():
            if body.winfo_manager():body.pack_forget();button.configure(text=title+' ▸')
            else:show()
        button.configure(command=toggle);body.show=show
        return body

    def build_history(self):
        bar = ttk.Frame(self.history)
        bar.pack(fill='x', pady=(0, 12))
        ttk.Button(bar, text='Export CSV', command=self.export).pack(side='left')
        ttk.Button(bar, text='Open selected screenshots', command=self.open_selected).pack(side='left', padx=8)
        ttk.Button(bar, text='Balance observations', command=self.show_balance_history).pack(side='left')
        ttk.Button(bar, text='Delete selected run', command=self.delete_selected).pack(side='right')
        self.edit_run_button = ttk.Button(bar, text='Edit selected run', command=self.edit_selected)
        self.edit_run_button.pack(side='right', padx=8)
        columns = ('day', 'points', 'money', 'included', 'notes', 'result')
        frame = ttk.Frame(self.history)
        frame.pack(fill='both', expand=True)
        self.tree = ttk.Treeview(frame, columns=columns, show='headings', selectmode='browse')
        self.tree.bind('<Double-1>', self.edit_selected)
        self.tree.bind('<Return>', self.edit_selected)
        for key, title, width in zip(columns, ('Game day', 'Points ±', 'Loot value', 'Already in stats', 'Notes', 'Result'),
                                     (110, 80, 130, 130, 250, 85)):
            self.tree.heading(key, text=title)
            self.tree.column(key, width=width, minwidth=60)
        self.tree.tag_configure('failed', foreground='#ffaaaa')
        scrollbar = ttk.Scrollbar(frame, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        spending_bar = ttk.Frame(self.history)
        spending_bar.pack(fill='x', pady=(14, 6))
        ttk.Label(spending_bar, text='BETWEEN-RUN SPENDING', font=('Segoe UI Semibold', 11)).pack(side='left')
        ttk.Button(spending_bar, text='Export spending CSV', command=self.export_spending).pack(side='right')
        ttk.Button(spending_bar, text='Delete selected expense', command=self.delete_expense).pack(side='right', padx=8)
        self.spend_tree = ttk.Treeview(self.history, columns=('day','amount','note'), show='headings', height=4, selectmode='browse')
        for key, title in [('day','Game day'), ('amount','Coins spent'), ('note','Note')]:
            self.spend_tree.heading(key, text=title)
        self.spend_tree.pack(fill='x')

    def build_settings(self):
        settings_root=self.settings_tab
        section_bar=ttk.Frame(settings_root);section_bar.pack(fill='x',pady=(0,18))
        self.settings_sections={title:ttk.Frame(settings_root) for title in ('General','Goals & budget','Shortcuts','Storage & updates')}
        self.settings_section=tk.StringVar(value='General')
        for title in self.settings_sections:
            ttk.Radiobutton(section_bar,text=title,value=title,variable=self.settings_section,command=self.show_settings_section,style='Chip.TRadiobutton').pack(side='left',padx=(0,6))
        general,planning,controls,storage_page=self.settings_sections.values()
        self.updates=UpdatesPanel(self,storage_page)
        language_box=ttk.LabelFrame(general,text='Interface language',padding=10)
        language_box.pack(fill='x',pady=(0,16))
        self.language_var=tk.StringVar(value=self.ledger.settings().get('language','en'))
        for language,label in LANGUAGES.items():
            ttk.Radiobutton(language_box,text=label,value=language,variable=self.language_var,command=lambda:self.set_language(self.language_var.get())).pack(side='left',padx=(0,18))
        ttk.Label(general,text='Changes apply immediately. Your data and shortcuts stay the same.',style='Muted.TLabel').pack(anchor='w',pady=(0,12))
        shortcuts=ttk.LabelFrame(controls,text='Shortcuts',padding=10)
        shortcuts.pack(fill='x',pady=(0,16))
        ttk.Label(shortcuts,text='Type a key or combination, such as ;, F8 or Ctrl+Shift+F8. Leave blank to disable.\nGame keys act only while Aniimo is focused and still reach the game. Map/close-map keys must match your game settings.',style='Muted.TLabel',wraplength=950).grid(row=0,column=0,columnspan=3,sticky='w',pady=(0,8))
        self.shortcut_vars={}
        for row,(action,label) in enumerate(LABELS.items(),start=1):
            ttk.Label(shortcuts,text=label).grid(row=row,column=0,sticky='w',padx=(0,18),pady=3)
            self.shortcut_vars[action]=tk.StringVar(value=self.shortcuts[action])
            ttk.Entry(shortcuts,textvariable=self.shortcut_vars[action],width=26).grid(row=row,column=1,sticky='w',pady=3)
            ttk.Label(shortcuts,text='Global' if action in GLOBAL_ACTIONS else 'Aniimo only',style='Muted.TLabel').grid(row=row,column=2,sticky='w',padx=12)
        keys_bar=ttk.Frame(shortcuts);keys_bar.grid(row=len(LABELS)+1,column=0,columnspan=3,sticky='w',pady=(8,0))
        ttk.Button(keys_bar,text='Save shortcuts',command=self.save_shortcuts,style='Accent.TButton').pack(side='left')
        ttk.Button(keys_bar,text='Restore default shortcuts',command=self.reset_shortcuts).pack(side='left',padx=8)
        self.setting_vars = {}
        storage=ttk.LabelFrame(storage_page,text='Screenshot storage',padding=10)
        storage.pack(fill='x',pady=(0,16))
        ttk.Label(storage,text='Keep screenshots for last X runs (0 = none)').pack(anchor='w')
        storage_row=ttk.Frame(storage);storage_row.pack(anchor='w',pady=(6,5))
        self.setting_vars['screenshot_runs']=tk.StringVar(value=str(self.ledger.settings()['screenshot_runs']))
        ttk.Entry(storage_row,textvariable=self.setting_vars['screenshot_runs'],width=9).pack(side='left')
        self.retention_button=ttk.Button(storage_row,text='Apply screenshot limit',command=self.save_screenshot_setting)
        self.retention_button.pack(side='left',padx=10)
        ttk.Label(storage,text='Default 30. Older screenshots are deleted automatically; run history and the current draft stay saved.',style='Muted.TLabel',wraplength=850).pack(anchor='w')
        grid = ttk.Frame(planning)
        grid.pack(fill='x')
        specs = [('target', 'Target Emperor eggs'), ('deadline', 'Deadline (YYYY-MM-DD, inclusive)'),
                 ('points_per_rank', 'Points per Emperor egg'), ('daily_tickets', 'Tickets to buy per day'),
                 ('normal_points', 'Expected normal points (before logged data)'),
                 ('first_points', 'Expected first-run award (before logged data)'),
                 ('run_minutes', 'Minutes in each run (1–15; default 12)'),
                 ('extra_minutes', 'Extra minutes per run (queue / buying / selling)'),
                 ('reset_hour', 'Daily reset hour in your PC timezone (0–23)'),
                 ('gear_price','Gear price per slot'),('gear_discount_price','Weekly discount price per slot'),
                 ('gear_discount_count','Discounted pieces per slot / week'),('gear_life','Runs each gear lasts'),
                 ('gear_slots','Gear slots replaced'),('key_price','Price per key'),
                 ('solo_keys','Keys per solo run'),('party_keys','Keys per party run'),
                 ('play_days_week','Days played per week'),('runs_per_play_day','Runs per play day (0 = daily ticket target)')]
        settings = self.ledger.settings()
        for i, (key, label) in enumerate(specs):
            row, col = divmod(i, 2)
            box = ttk.Frame(grid)
            box.grid(row=row, column=col, sticky='ew', padx=(0, 20), pady=5)
            ttk.Label(box, text=label, style='Muted.TLabel').pack(anchor='w')
            var = tk.StringVar(value=str(settings[key]))
            self.setting_vars[key] = var
            ttk.Entry(box, textvariable=var).pack(fill='x', pady=2)
        for col in (0, 1):
            grid.columnconfigure(col, weight=1)
        screen_box = ttk.LabelFrame(general,text='Game capture',padding=12)
        screen_box.pack(fill='x',pady=12)
        ttk.Label(screen_box,text='Capture target',style='Muted.TLabel').pack(anchor='w')
        capture_row=ttk.Frame(screen_box);capture_row.pack(fill='x',pady=4)
        self.capture_target_var=tk.StringVar()
        self.capture_target_choice=ttk.Combobox(capture_row,state='readonly',textvariable=self.capture_target_var)
        self.capture_target_choice.pack(side='left',fill='x',expand=True)
        self.capture_target_choice.bind('<<ComboboxSelected>>',lambda event:self.select_capture_target())
        ttk.Button(capture_row,text='Refresh windows',command=self.refresh_capture_targets).pack(side='right',padx=(8,0))
        self.refresh_capture_targets()
        ttk.Label(screen_box,text='Window capture follows the game client area as it moves or resizes. Keep the game visible. Monitor capture is a manual fallback.',style='Muted.TLabel',wraplength=700).pack(anchor='w',pady=(2,8))
        ttk.Label(screen_box, text='Fallback monitor (used only for Entire monitor)', style='Muted.TLabel').pack(anchor='w')
        self.screens = monitors()
        self.monitor_choice = ttk.Combobox(screen_box, state='readonly', values=[
            f"{m['name']}  ·  {m['bbox'][2]-m['bbox'][0]}×{m['bbox'][3]-m['bbox'][1]}" + ('  · primary' if m['primary'] else '')
            for m in self.screens])
        self.monitor_choice.pack(fill='x', pady=2)
        self.monitor_choice.current(min(settings['monitor'], len(self.screens)-1))
        self.budget_party=tk.BooleanVar(value=settings['budget_party'])
        ttk.Checkbutton(planning,text='Party budget (use party key count)',variable=self.budget_party).pack(anchor='w')
        ttk.Label(planning, text='Daily ticket prices, first through twentieth (editable community values)',
                  style='Muted.TLabel').pack(anchor='w', pady=(16, 4))
        self.price_var = tk.StringVar(value=', '.join(str(n) for n in (settings['prices'] or PRICES)))
        ttk.Entry(planning, textvariable=self.price_var).pack(fill='x')
        ttk.Label(planning, text='Use Correct current stats to set total points, tickets or your actual balance.\n'
                  'Averages use successful runs, including daily bonuses; failed runs are excluded.\n'
                  'Ticket purchases are logged manually; the daily target is used only for planning.',
                  style='Muted.TLabel', wraplength=1000).pack(anchor='w', pady=16)
        self.show_settings_section()
        bar = self.settings_save_bar = ttk.Frame(settings_root)
        bar.pack(fill='x',pady=(16,0))
        ttk.Button(bar, text='Save settings', command=self.save_settings, style='Accent.TButton').pack(side='left')
        ttk.Button(bar, text='Correct current stats', command=self.correct_stats_dialog).pack(side='left', padx=8)
        ttk.Button(bar, text='Open data folder', command=lambda: os.startfile(self.data_dir)).pack(side='left', padx=8)

    def show_settings_section(self):
        for title,frame in self.settings_sections.items():
            frame.pack_forget()
        frame=self.settings_sections[self.settings_section.get()]
        # Keep the shared save controls below the selected section.
        bar=getattr(self,'settings_save_bar',None)
        if bar:frame.pack(fill='x',before=bar)
        else:frame.pack(fill='x')

    def shortcut_hint(self,action):
        return self.shortcuts[action] or 'not assigned'

    def set_language(self,language):
        activate_language(language)
        self.ledger.configure(language=language)
        self.language_var.set(language)
        self.localizer.refresh(self);self.localizer.refresh()
        self.sanctum.overlay_dirty=True;self.sanctum.paint()
        self.analytics.refresh()
        self.status.set('Language updated')

    def apply_shortcuts(self,values):
        values={action:values.get(action,default).strip() for action,default in DEFAULT_SHORTCUTS.items()}
        specs=compile_shortcuts(values)
        old_specs=self.shortcut_specs
        temp=self.shortcuts_path.with_suffix('.tmp')
        temp.write_text(json.dumps(values,ensure_ascii=False),encoding='utf-8')
        if self.hk:self.hk.close()
        new=None
        try:
            new=Hotkeys(specs) if self.hotkeys_enabled else None
            if new and new.failed:
                failed=', '.join(LABELS[action]+' ('+values[action]+')' for action in GLOBAL_ACTIONS if ACTION_IDS[action] in new.failed)
                raise ValueError('Unavailable or already in use: '+failed+'. Previous shortcuts were restored.')
            if new and not new.map_hook:
                raise ValueError('The game-key listener could not start. Previous shortcuts were restored.')
            temp.replace(self.shortcuts_path)
        except Exception:
            if new:new.close()
            self.hk=Hotkeys(old_specs) if self.hotkeys_enabled else None
            raise
        self.hk=new
        self.shortcuts,self.shortcut_specs=values,specs
        for action,var in self.shortcut_vars.items():var.set(values[action])
        self.capture_button.configure(text=f'Capture screen · {self.shortcut_hint("capture")}')
        self.sanctum.update_shortcut_hints()
        if hasattr(self,'nav_hint'):self.nav_hint.set(f'CAPTURE\n{self.shortcut_hint("capture")}\n\nOVERLAY\n{self.shortcut_hint("overlay")}')
        for widget in self.help_tab.winfo_children():widget.destroy()
        self.build_help()
        self.update_run_status()
        self.status.set('Shortcuts saved and active. Overlay toggle: '+self.shortcut_hint('overlay'))

    def save_shortcuts(self):
        try:self.apply_shortcuts({action:var.get() for action,var in self.shortcut_vars.items()})
        except Exception as exc:messagebox.showerror(tr('Check shortcuts'),tr(str(exc)))

    def reset_shortcuts(self):
        try:self.apply_shortcuts(DEFAULT_SHORTCUTS)
        except Exception as exc:messagebox.showerror(tr('Check shortcuts'),tr(str(exc)))

    def build_help(self):
        text = tk.Text(self.help_tab, bg=PANEL, fg=TEXT, wrap='word', font=('Segoe UI', 11),
                       relief='flat', padx=20, pady=20)
        text.pack(fill='both', expand=True)
        text.insert('1.0', '''YOUR RUN WORKFLOW

1. Keep the tracker open or minimized while you play Aniimo on DISPLAY1.
2. Start run accepts a manually entered Balance (optional); leave it blank if unknown. Or capture Inventory with Ctrl+Shift+F8 to start with an observed balance. An unrecognized automatic capture starts without a balance if no run or unsaved result exists. The overlay header says Waiting for map until a full map confirms the layout. No ticket is consumed yet. For just the map, use Map > Start map tracker without creating a run.
3. Enter Chaos and open M once with both portals visible. After the full map is recognized, close M; the overlay follows the minimap. Lobby minimap matches cannot select a layout. The same Capture screen action can read an open M map or resume an already confirmed map from gameplay.
4. At the end, capture points with Ctrl+Shift+F8 or type them. Loot is optional: type/capture it if known, or leave blank. Blank loot is Unknown, not zero. Quick successive captures are queued. The overlay can show loot/points readings and the Save ready run shortcut (Ctrl+Shift+F9 by default); it saves only valid results after all readings finish. Saving ends navigation. Enable Keep status bar between runs in Map > Overlay to retain a compact in-game header between runs. All shortcuts can be changed in Settings.
5. Check the points and click Save run. This also works with no recorded start or screenshots. Points and one ticket are counted once; loot value never adds cash.

Map & routes uses one Pause map / Resume map toggle in both tracked-run and map-only modes. The same configurable Toggle map tracking shortcut does both. Without a run, Start map tracker begins map-only mode. An Inventory capture switches into run logging automatically; capturing points or entering points and saving also records a result. Gameplay and map captures alone do not record runs. Pause preserves the detected layout. Every game-map key press requests a fresh full-map check before minimap following. Unknown screenshots do not change stats.
The Tickets on hand card has Buy tickets (log an actual purchase) and Free tickets (chest/reward receipts). Free tickets do not charge coins or use daily paid shop slots. Both update stock and forecasts immediately; free-ticket receipts remain in that dialog's history. Correct stats is directly under Total points.
More options contains optional spending, manual inputs, image imports, reading areas and cancel-start controls. Map & routes puts difficulty, route goals and icon switches beside the preview. Choose Route, Icons, Overlay or Tools in the map sidebar. Overlay contains display controls and Tools contains calibration and the optional simulator.
For history already reflected in your stats, check Already included in current stats under More options. The supplied 431,719-loot / 192-point example is included this way. Cancel mistaken run start and Clear result draft are also under More options.

LOCAL TEXT RECOGNITION

Windows OCR runs on your computer. Nothing is uploaded and no API key is needed. Suggested reading areas are calibrated from your three example screens. Use “Set reading area” to change them after changing resolution/UI scale. Only a single clear number is accepted. The inventory abbreviation 9637.5 K means approximately 9,637,500; the game may hide finer precision. Enter a full balance in Correct current stats when you know it. “Show OCR text” displays the readings.
Loot is read next to Saque da partida / Match loot on the full result screen, so shifted text does not require adjusting a fixed crop. The saved reading area remains a fallback. Defeat counts and timers are not used as loot values.

You can also import screenshots. Manual values work even when OCR fails. Screenshots may be black in exclusive fullscreen; use borderless/windowed mode if needed.

PLANNING AND COINS

Correct current stats sets total points, tickets or balance directly. Optional advanced calibration accepts the Emperor egg count and within-egg progress. It preserves history; older events are already included in the corrected values. New runs and purchases then apply from that point onward. You do not need to calculate a new starting baseline. The deadline includes the entire selected game day. Daily reset uses your PC’s timezone; set it to match your server reset.

Lifetime points are cumulative across earlier tiers. They cannot be divided directly by 180 to find your Emperor rank. The default Egg Emperor threshold is 14,550 total points, inferred from 47,723 total minus 184 eggs × 180 minus 53 progress. Before that threshold, the overview shows total points; after it, the Emperor egg count is also shown. Correct current stats accepts total points directly. Advanced > calibrate eggs can recalibrate using total, eggs and within-egg progress from the same screen. Result OCR reads the total separately from the signed run award; saving can reconcile the first known total too.

Run loot value is not cash income. You can keep items, sell them later, or receive a different sale price. Your latest observed inventory balance is authoritative. Subsequent recorded purchases/spending reduce the estimate; run loot never increases it. The difference between successive start balances includes all intervening sales and spending and is not individual run profit.

Forecasts assume you buy the configured daily tickets and use your stockpile. They assume you can afford the purchases. Logged point changes are used exactly: 400 adds 400 and -140 loses 140. Once you have logged successful Chaos runs, the forecast uses their actual average, including daily bonuses, and adds no further daily bonus. Failed runs still change rank progress and ticket stock, but are excluded from average points per successful run. Before any successful Chaos runs, expected normal and first-daily awards are used. Early averages can be noisy. Non-ticket runs do not train the Chaos average.
Failed run is beside the Points field. Check it and enter points lost as a positive amount (140), or enter -140 directly. Enter 0 with Failed run checked for a zero-point failure. Save run records the result and ticket use once. Run history marks failed results and lets you edit their loss or outcome. A failure never fabricates a loot value or credits cash; optional loot remains separate. Already included in current stats and newer authoritative corrections still take priority.
Overview estimates playtime as remaining runs times 12 minutes by default: a 15-minute run ending with 3 minutes left. Change Minutes in each run and optional Extra minutes per run in Settings to account for queues, buying or selling. Daily time is an average over every calendar day until the deadline; skipped days mean more time on the days you play. Estimates update after saved/edited runs and stat corrections; they are not measured playtime.

RESEARCH · CHECKED OCTOBER 18, 2026

Community table (AniiGuide): tickets 1/2/3 cost 20k/50k/70k; 4–6 cost 100k each; 7–10 cost 200k; 11–15 cost 300k; 16–20 cost 400k. Thus 15 cost 2,740,000 and 20 cost 4,740,000. Prices are editable and need confirmation against your live shop.
https://aniiguide.trade/
https://dailyaniimo.com/guides/chaos-mode

The dashboard break-even budget includes ticket purchases, keys, and replacement gear. Defaults: two slots at 120k each, lasting two runs; first three pieces per slot each week cost 60k; keys cost 100k each, two solo or one in a party. Weekly replacement sets are rounded up. Tickets are bought every day; play days and runs per play day can be set separately for this cash budget. This is a planning estimate, not an automatic wallet deduction. It excludes extra losses and other purchases. Actual spending stays in the ledger. Revenue must be sold to fund purchases; extracted loot value can remain in inventory. Log ticket purchase adds tickets and deducts its cost; the next inventory observation already includes those purchases.

DATA AND RECOVERY

Run history > Edit selected run (or double-click a row) corrects points, optional loot, expenses, date, notes and counting options. Save changes keeps the same entry and screenshots without ending an ongoing run. Blank loot means Unknown. Edits recalculate totals and forecasts, but newer authoritative stat corrections take priority over older results.
Analytics shows loot/logged costs, wallet checkpoints, points and tickets for Today, 7, 30 or 90 days, or All time. Run details supports sorting, editing and CSV export for the selected period. Estimated loot/hour uses configured run time; loot minus planned cost is an item-value comparison, not cash profit. Hover for exact values. Starting balance supplies a wallet checkpoint after your sales and shopping. Checkpoint changes include all intervening sales and spending, not individual run profit. Unknown loot stays missing. Hollow wallet dots are estimates; Wallet now always shows the latest all-time value. Failed runs do not train successful-run averages.
All data is in %LOCALAPPDATA%\\AniimoTracker. Back up that folder (tracker.db and screenshots) to keep everything. Drafts and active starts survive restarts. CSV exports include screenshot paths. Balance observations and corrections are available in history. Deleting a run undoes progress only when that progress was added after the latest authoritative correction; it never changes an observed balance. Close the tracker to release its shortcuts.
''')
        text.insert('end','\n\nSCREENSHOT STORAGE\n\nSettings > Screenshot storage keeps images for the last 30 saved runs by default. Change the limit and Apply screenshot limit; 0 keeps no saved-run screenshots. Older result and starting-balance images are deleted automatically. History, stats, notes, active-run screenshots and the current draft remain. Unused tracker captures are cleaned up too. Increasing the limit cannot restore deleted images; exported paths may refer to expired screenshots.\n')
        content=text.get('1.0','end-1c').replace('Ctrl+Shift+F8',self.shortcut_hint('capture'))
        content=content.replace('Ctrl+Shift+F9',self.shortcut_hint('save'))
        content=content.replace('open M','open '+self.shortcut_hint('map')).replace('close M','close '+self.shortcut_hint('map'))
        text.delete('1.0','end');text.insert('1.0',content)
        text.configure(state='disabled')
        self.localizer.register_text(text,content,HELP_PT_BR.format(capture=self.shortcut_hint('capture'),save=self.shortcut_hint('save'),map=self.shortcut_hint('map')))

    def refresh(self):
        self.screenshot_cleanup_due=True
        if hasattr(self,'analytics'):
            self.analytics.refresh()
        if hasattr(self,'sanctum'):
            self.sanctum.sync_run()
            if hasattr(self,'party'):self.party.sync_context()
        state, plan = self.ledger.summary(), forecast(self.ledger)
        s = self.ledger.settings()
        known=state['total_points'] is not None
        for key, value in dict(rank=f"{state['total_points']:,}" if known else '—', tickets=str(state['tickets']),
                                today=f"{state['today_points']:,}", net=('≈ ' if state['coins_approximate'] else '') + f"{state['coins']:,}").items():
            self.card_values[key].set(value)
        self.progress_caption.set((f"Egg Emperor · {state['eggs']:,} eggs · {state['rank_points']}/{s['points_per_rank']}" if state['is_emperor'] else
            f"{state['emperor_threshold']-state['total_points']:,} points to Egg Emperor") if known else 'Set your current total points')
        self.balance_source_text.set('Estimated since last check' if state['coins_estimated'] else 'Latest observed balance')
        if not known:
            line='Set your total points to calculate this goal.'
        elif not state['remaining']:
            line = 'Goal reached!'
        elif plan['reachable']:
            line = f"On track · {s['target']:,} eggs by {plan['finish']:%b %d} · {plan['needed_tickets']:,} runs left"
        else:
            line = f"Below target at this pace · {state['remaining']:,} points left · adjust goal settings"
        self.forecast_text.set(line)
        goal_points=max(1,state['emperor_threshold']+s['target']*s['points_per_rank'])
        progress=max(0,min(100,100*state['total_points']/goal_points)) if known else 0
        self.goal_progress.configure(value=progress)
        self.goal_progress_text.set((f"Total points {state['total_points']:,} / {goal_points:,} · {progress:.1f}%") if known else f"Target: {goal_points:,} total points · {s['target']:,} eggs")
        if not known:
            time_line='Estimated playtime: — · set your total points first'
        elif not state['remaining']:
            time_line = 'Goal reached · 0 min of playtime remaining'
        elif plan['play_minutes'] is None:
            time_line = 'Playtime estimate unavailable · successful-run points per run must be positive'
        else:
            time_line = f"Estimated playtime: {self.duration(plan['session_minutes'])} total"
            if plan['daily_session_minutes'] is not None:
                time_line += f" · ≈ {self.duration(plan['daily_session_minutes'])}/calendar day"
            else:
                time_line += ' · deadline has passed'
        self.playtime_text.set(time_line)
        runs = self.ledger.runs()
        budget=break_even(s)
        self.budget_panel.update_budget(s,budget)
        self.budget_text.set(self.budget_panel.details.get())
        margin=f"{plan['margin']:+,}" if plan['margin'] is not None else '—'
        self.goal_details_text.set(
            f"Deadline: {s['deadline']} · {plan['days']} days left · {margin} ticket margin\n"
            f"{state['normal']:.1f} pts/success · {s['run_minutes']} min/run + {s['extra_minutes']} extra min/run\n"
            'Assumes daily ticket purchases. Daily time includes days off.')
        self.tree.delete(*self.tree.get_children())
        for run in runs:
            self.tree.insert('', 'end', iid=str(run['id']), values=(run['day'], run['points'],
                'Unknown' if run['money'] is None else f"{run['money']:,}", 'Yes' if not run['applied'] else '', run['notes'],
                'Failed' if run['failed'] else 'Completed'), tags=('failed',) if run['failed'] else ())
        self.spend_tree.delete(*self.spend_tree.get_children())
        for expense in self.ledger.spending():
            self.spend_tree.insert('', 'end', iid=str(expense['id']), values=(expense['day'], f"{expense['amount']:,}", expense['note']))
        active = self.ledger.active_start()
        self.manual_start_button.configure(state='disabled' if active else 'normal')
        self.start_balance_entry.configure(state='disabled' if active else 'normal')
        if active:
            balance_info=('starting balance not recorded · wallet estimate unchanged' if active['balance'] is None else
                'inventory balance '+('≈ ' if active['approximate'] else '')+f"{active['balance']:,} · loot results will not add cash")
            self.run_info.set(f"Run started {active['timestamp']} · "+balance_info)
        else:
            self.run_info.set('Map tracker active · capture Inventory to start a run, or capture/enter points and Save run.' if self.sanctum.session.standalone else
                'No run active. Start run accepts a manual balance or a blank balance. You can also enter points directly below.')
        self.update_run_status()

    def update_run_status(self):
        active=self.ledger.active_start()
        valid=[]
        for kind in ('money','points'):
            try:
                (parse_points if kind == 'points' else parse_amount)(self.fields[kind].get())
                valid.append(kind)
            except ValueError:
                pass
        reading=self.busy_capture or self.auto_busy or bool(self.auto_pending)
        self.save_run_button.configure(state='normal' if not self.sanctum.session.standalone or 'points' in valid else 'disabled')
        if active:
            map_state=('Map watching' if self.sanctum.session.map_confirmed else 'Map waiting for '+self.shortcut_hint('map')) if self.sanctum.session.watching else 'Map paused'
            heading='Run ongoing'
            if reading:
                guidance='Reading screenshot… You can keep playing or capture the next screen.'
            elif len(valid)==2:
                guidance='Loot and points ready. Check the values, then Save run to finish.'
            elif 'points' in valid:
                guidance='Points ready · loot is optional. Save run whenever you are finished.'
            elif valid:
                guidance=f'Capture points with {self.shortcut_hint("capture")}, or type them, then Save run.'
            else:
                guidance=f'When finished, capture points with {self.shortcut_hint("capture")}, or type them, then Save run. Loot is optional.'
                if self.sanctum.session.watching and not self.sanctum.session.map_confirmed:
                    guidance=f'Enter {self.sanctum.difficulty.get()} and open the map ({self.shortcut_hint("map")}) with both portals visible. The overlay waits for confirmation.'
            self.run_heading.set(f'{heading} · {map_state}')
        else:
            self.run_heading.set(('Map tracker only · '+('Watching' if self.sanctum.session.watching else 'Paused')) if self.sanctum.session.standalone else 'Results to save' if valid else 'Between runs · No active run')
            guidance=('Check the result values, then Save run.' if valid else
                f'Capture Inventory with {self.shortcut_hint("capture")} to start, or type results below to log a manual run.')
            if reading:guidance='Reading screenshot…'
            elif self.sanctum.session.standalone:
                guidance=('Points ready · Save run to record this result. Loot is optional.' if 'points' in valid else
                    'Capture or enter points, then Save run.' if valid else
                    'Map-only tracking · capture Inventory to start a run, or capture points to log a result.' if self.sanctum.session.map_confirmed else
                    f'Map only · no stats are recorded. Open the game map ({self.shortcut_hint("map")}) to confirm the layout.')
        self.run_guidance.set(guidance)

    def capture_image(self, kind, from_button=False):
        if self.updates.restart_pending:return
        if kind == 'balance' and not self.can_start_capture():
            return
        if self.busy_capture:
            return
        self.busy_capture = True
        self.status.set(f'Capturing {kind} in 0.4s…')
        # Hide this window if the button was used, so it cannot obscure the game.
        self.capture_restore = from_button and self.state() != 'iconic'
        if self.capture_restore:
            self.withdraw()
        self.after(400, lambda: self.finish_capture(kind))

    def finish_capture(self, kind):
        try:
            path = self.data_dir / 'screenshots' / f'{datetime.now():%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:8]}_{kind}.png'
            settings=self.ledger.settings()
            capture(path,settings['monitor'],settings['capture_target'])
            if kind=='auto':self.auto_attach(path)
            else:self.attach(kind,path)
        except Exception as exc:
            self.status.set(f'Capture failed: {exc}')
        finally:
            self.busy_capture = False
            if self.capture_restore:
                self.deiconify()

    def import_image(self, kind):
        if kind == 'balance' and not self.can_start_capture():
            return
        name = filedialog.askopenfilename(filetypes=[(tr('Images'), '*.png *.jpg *.jpeg *.bmp *.webp')])
        if name:
            try:
                dest = self.data_dir / 'screenshots' / f'{uuid.uuid4().hex}_{kind}.png'
                with Image.open(name) as im:
                    im.convert('RGB').save(dest)
                self.attach(kind, dest)
            except Exception as exc:
                messagebox.showerror(tr('Import failed'), tr(str(exc)))

    def attach(self, kind, path, full_text=None):
        if self.sanctum.session.standalone:
            previous=self.capture_context()
            self.sanctum.stop_map_only()
            self.transfer_pending_captures(previous)
        self.screenshot_cleanup_due=True
        self.draft_images[kind] = str(path)
        self.fields[kind].set('')
        self.capture_labels[kind].set(f'Attached · {Path(path).name[:35]}')
        self.persist_draft()
        self.start_ocr(kind,full_text=full_text)

    def capture_context(self):
        active=self.ledger.active_start()
        return (active['id'] if active else None,len(self.ledger.runs()),self.sanctum.context_serial)

    def transfer_pending_captures(self,previous):
        """Keep one capture burst together during an automatic run start."""
        current=self.capture_context()
        self.auto_pending=[(path,current if context==previous else context) for path,context in self.auto_pending]

    def auto_attach(self,path,context=None):
        """The one capture action; classify first, then use the normal review path."""
        self.screenshot_cleanup_due=True
        context=self.capture_context() if context is None else context
        difficulty=self.sanctum.difficulty.get()
        if self.auto_busy or self.pending_ocr:
            self.auto_pending.append((path,context))
            self.status.set('Screenshot queued. Reading the previous capture…')
            return
        self.auto_busy=True
        self.capture_button.configure(text='Capture screen · reading last capture…',state='normal')
        self.status.set('Reading screen locally…')
        def work():
            kind,reading,text,error=None,{},'',None
            try:
                text=recognize(path)
                kind=screen_kind(text)
            except Exception as exc:error=str(exc)
            if kind is None:
                try:
                    from sanctum import Detector
                    with Image.open(path) as im:
                        reading=Detector(self.data_dir/'sanctum/calibration',difficulty).detect(im)
                    if len(reading.get('candidates',[]))==1:kind='map'
                    else:
                        with Image.open(path) as im:
                            match=self.auto_maps.identify(im,self.sanctum.config.get('minimap_region'))
                        if match:
                            kind='gameplay';reading={'match':match}
                except Exception:pass
            self.auto_messages.put((context,kind,str(path),text,reading,error))
        threading.Thread(target=work,daemon=True).start()

    def start_ocr(self, kind, full_text=None):
        self.pending_ocr.add(kind)
        self.generations[kind] += 1
        generation = self.generations[kind]
        path = self.draft_images[kind]
        regions = {**DEFAULT_REGIONS, **self.ledger.settings()['regions']}
        region = regions.get(kind)
        self.status.set(f'{kind.capitalize()} captured · reading text locally…')
        def work():
            try:
                totals=None;point_change=None
                if kind=='money':
                    # Loot moves with result-screen wrapping. Prefer the number
                    # attached to its label; reuse classification OCR if present.
                    result=full_text if full_text is not None else recognize(path)
                    if loot_reading(result) is None:
                        result=recognize(path,region)
                elif kind=='points':
                    full=full_text if full_text is not None else recognize(path)
                    point_change=rank_points_reading(full)
                    totals=lifetime_reading(full)
                    # A tight crop can turn the cross of +370 into a dash.
                    # Keep the explicit sign read in the full ranking context.
                    result=f'{point_change:+d}' if point_change is not None else recognize(path,region)
                else:
                    result = recognize(path, region)
                if kind == 'points' and totals is None:
                    try:
                        totals = lifetime_reading(recognize(path, regions['lifetime']))
                    except Exception:
                        pass
                trusted=bool(region) or point_change is not None or (kind=='money' and loot_reading(result) is not None)
                self.messages.put((kind, generation, result, trusted, None, totals))
            except Exception as exc:
                self.messages.put((kind, generation, '', bool(region), str(exc), None))
        threading.Thread(target=work, daemon=True).start()

    def poll_map_input(self):
        # Keep M/Esc responsive without increasing capture/render frequency.
        self.sanctum.poll_map_keys()
        self.map_input_tick_id = self.after(16, self.poll_map_input)

    def tick(self):
        self.updates.tick()
        if self.updates.restart_pending:return
        self.party.tick()
        self.sanctum.tick()
        self.update_run_status()
        if self.hk:
            for key in self.hk.poll():
                if key == 1:
                    self.capture_image('auto')
                elif key == 2:self.quick_save_run()
                elif key == 5:
                    self.sanctum.overlay_enabled.set(not self.sanctum.overlay_enabled.get())
                    self.sanctum.toggle_overlay()
                    self.status.set('Overlay '+('shown' if self.sanctum.overlay_enabled.get() else 'hidden')+' · run and tracking unchanged')
                elif key == 6:self.sanctum.toggle_move()
                elif key == 7:self.sanctum.watch_action()
                elif key == 3:
                    # Never steal focus from a running game to ask about clearing.
                    if any(self.fields[k].get() for k in ('money', 'points')) or self.draft_images:
                        self.status.set('Draft has unsaved data. Return to the tracker and use Clear draft.')
                    else:
                        self.clear_draft(confirm=False)
        while not self.auto_messages.empty():
            context,kind,path,text,reading,error=self.auto_messages.get_nowait()
            self.auto_busy=False
            self.capture_button.configure(text=f'Capture screen · {self.shortcut_hint("capture")}',state='normal')
            if context!=self.capture_context():
                self.status.set('The run changed while reading this screenshot. Capture it again if needed.')
                continue
            if kind in ('money','points','balance'):
                if kind=='balance' and self.ledger.active_start():
                    self.status.set('Your run is already active. Capture loot and points when it finishes.')
                    continue
                self.attach(kind,path,full_text=text if kind in ('money','points') else None)
                if kind in ('money','points'):self.tabs.select(0)
            elif kind=='map':
                panel=self.sanctum
                if panel.session.context_id is not None:panel.resume_watch()
                with Image.open(path) as im:panel.last_image=im.convert('RGB')
                panel.last_reading=reading
                panel.accept_layout(reading['candidates'][0],reading)
                panel.session.observe_screen('full_map')
                panel.last_image.save(panel.folder/'last-map.png')
                self.status.set('Map refreshed. Close the game map and continue playing.')
            elif kind=='gameplay' and self.sanctum.session.context_id is not None:
                if not self.sanctum.session.map_confirmed:
                    self.status.set('Run active. Open the game map inside Chaos once to confirm it; lobby minimaps cannot start the overlay.')
                    continue
                self.sanctum.resume_watch()
                match=reading.get('match')
                if match:
                    panel=self.sanctum
                    if panel.engine and match['layout']!=panel.engine.layout:
                        self.status.set('Minimap does not match the confirmed layout. Open the game map to confirm it.')
                        continue
                    panel.accept_layout(match['layout'],{})
                    panel.player=match['player'];panel.position_time=time.monotonic()
                    panel.session.observe_screen('minimap');panel.overlay_dirty=True
                    panel.config['player']=panel.player;panel.write_config();panel.paint()
                self.status.set('Gameplay detected. Map tracking resumed on your current run.')
            else:
                if not self.ledger.active_start() and not self.sanctum.session.standalone and self.can_start_capture():
                    self.begin_run(without_balance=True)
                    self.status.set('Run started without balance · screen unrecognized · waiting for map')
                else:self.status.set('Screen unrecognized · current run and stats unchanged')
        while not self.messages.empty():
            kind, gen, text, cropped, error, totals = self.messages.get_nowait()
            if gen != self.generations[kind]:
                continue
            self.pending_ocr.discard(kind)
            self.ocr_text[kind] = text
            value = (loot_reading(text,allow_unlabelled=True) if kind=='money' else
                     (single_points if kind == 'points' else single_amount)(text))
            if not error and cropped and value is not None and not self.fields[kind].get():
                self.fields[kind].set(str(value))
                if kind == 'points' and value < 0:
                    self.failed_run.set(True)
                elif kind=='points' and text.strip().startswith('+'):
                    self.failed_run.set(False)
                self.status.set(f'{kind.capitalize()} value read · review before saving')
                if kind == 'balance':
                    self.balance_approximate = bool(re.search(r'[KkMmBb]', text))
                    self.begin_run()
            elif error:
                self.status.set(f'OCR unavailable: {error[:130]} · enter the value manually')
            else:
                self.status.set(f'{kind.capitalize()} text ready · set a reading area or enter the value manually')
            if kind=='balance' and (error or value is None):
                self.more_options.show()
            if kind == 'points' and totals and not self.fields['lifetime'].get():
                self.fields['lifetime'].set(str(totals[0]))
            self.persist_draft()
        if not self.auto_busy and not self.pending_ocr and self.auto_pending:
            path,context=self.auto_pending.pop(0)
            self.auto_attach(path,context)
        if time.monotonic()>=self.next_locale_refresh:
            self.localizer.refresh()
            self.next_locale_refresh=time.monotonic()+.5
        if self.screenshot_cleanup_due and time.monotonic()>=self.next_screenshot_cleanup:
            self.cleanup_screenshots()
        self.tick_id = self.after(100, self.tick)

    def view_image(self, kind):
        path = self.draft_images.get(kind)
        if path:
            os.startfile(path)
        else:
            messagebox.showinfo(tr('No image'), tr('Capture or import a screenshot first.'))

    def choose_region(self, kind):
        path = self.draft_images.get(kind)
        if not path:
            messagebox.showinfo(tr('Reading area'), tr('Capture or import a screenshot of this result screen first.'))
            return
        window = tk.Toplevel(self)
        window.title(f'{kind.capitalize()} · drag a box around JUST the number')
        with Image.open(path) as source:
            im = source.copy()
        im.thumbnail((min(1200, self.winfo_screenwidth()-100), self.winfo_screenheight()-180))
        photo = ImageTk.PhotoImage(im)
        canvas = tk.Canvas(window, width=im.width, height=im.height, highlightthickness=0)
        canvas.pack()
        canvas.create_image(0, 0, image=photo, anchor='nw')
        canvas.photo = photo
        selection = {}
        def press(event):
            canvas.delete('selection')
            selection['start'] = (event.x, event.y)
        def drag(event):
            if 'start' in selection:
                canvas.delete('selection')
                canvas.create_rectangle(*selection['start'], event.x, event.y, outline='#68e1b9', width=3, tags='selection')
        def release(event):
            if 'start' not in selection:
                return
            x, y = selection['start']
            x1, x2 = sorted((max(0, min(x, im.width)), max(0, min(event.x, im.width))))
            y1, y2 = sorted((max(0, min(y, im.height)), max(0, min(event.y, im.height))))
            if x2-x1 > 5 and y2-y1 > 5:
                selection['region'] = [x1/im.width, y1/im.height, x2/im.width, y2/im.height]
        def save():
            if 'region' not in selection:
                return
            regions = self.ledger.settings()['regions'].copy()
            regions[kind] = selection['region']
            self.ledger.configure(regions=regions)
            window.destroy()
            self.start_ocr(kind)
        def reset():
            regions = self.ledger.settings()['regions'].copy()
            regions.pop(kind, None)
            self.ledger.configure(regions=regions)
            window.destroy()
            self.start_ocr(kind)
        canvas.bind('<ButtonPress-1>', press)
        canvas.bind('<B1-Motion>', drag)
        canvas.bind('<ButtonRelease-1>', release)
        bar = ttk.Frame(window, padding=8)
        bar.pack(fill='x')
        ttk.Button(bar, text='Save reading area & read', command=save).pack(side='left')
        ttk.Button(bar, text='Use suggested area', command=reset).pack(side='left', padx=8)

    def show_ocr(self):
        window = tk.Toplevel(self)
        window.title('Recognized text · inspect before entering values')
        text = tk.Text(window, width=95, height=30, bg=PANEL, fg=TEXT, wrap='word')
        text.pack(fill='both', expand=True)
        for kind in ('balance', 'money', 'points'):
            text.insert('end', f'{kind.upper()}\n{self.ocr_text.get(kind, "No recognized text yet.")}\n\n')
        text.configure(state='disabled')

    def persist_draft(self):
        self.ledger.save_draft(dict(images=self.draft_images, fields={k:v.get() for k,v in self.fields.items()},
            consumes=self.consumes.get(), day=self.run_day.get(), notes=self.notes.get(),
            spending_amount=self.spend_amount.get(), spending_note=self.spend_note.get(),
            already_included=self.already_included.get(), balance_approximate=self.balance_approximate,
            failed=self.failed_run.get()))

    def restore_draft(self):
        self.ocr_text = {}
        draft = self.ledger.draft()
        self.draft_images = draft.get('images', {})
        for k, v in draft.get('fields', {}).items():
            if k in self.fields:
                self.fields[k].set(v)
        for k in self.draft_images:
            self.capture_labels[k].set('Restored screenshot attached')
        self.spend_amount.set(draft.get('spending_amount', ''))
        self.spend_note.set(draft.get('spending_note', ''))
        # Preserve unsaved costs from the previous version by moving them to spending.
        old_expense = draft.get('fields', {}).get('expenses', '0')
        if not self.spend_amount.get() and old_expense not in ('', '0'):
            self.spend_amount.set(old_expense)
        self.consumes.set(draft.get('consumes', True))
        self.already_included.set(draft.get('already_included', False))
        self.failed_run.set(draft.get('failed', False))
        self.balance_approximate = draft.get('balance_approximate', False)
        self.run_day.set(draft.get('day', str(self.ledger.game_day())))
        self.notes.set(draft.get('notes', ''))

    def clear_draft(self, confirm=True):
        if confirm and not messagebox.askyesno(tr('Clear draft'), tr('Clear this unsaved run? Its screenshot files will be kept.')):
            return
        for key in ('money', 'points'):
            self.generations[key] += 1
            self.pending_ocr.discard(key)
            self.fields[key].set('')
            self.capture_labels[key].set('No screenshot attached')
        self.fields['lifetime'].set('')
        self.already_included.set(False)
        self.failed_run.set(False)
        self.draft_images = {k:v for k,v in self.draft_images.items() if k == 'balance' and self.ledger.active_start()}
        if not self.ledger.active_start():
            self.generations['balance'] += 1
            self.pending_ocr.discard('balance')
            self.fields['balance'].set('')
        self.ocr_text = {}
        self.notes.set('')
        self.run_day.set(str(self.ledger.game_day()))
        self.persist_draft()
        self.screenshot_cleanup_due=True

    def cleanup_screenshots(self):
        if (self.busy_capture or self.auto_busy or self.auto_pending or self.pending_ocr or
            not self.messages.empty() or not self.auto_messages.empty()):return
        try:
            result=prune_screenshots(self.ledger,self.data_dir/'screenshots',protected=self.draft_images.values())
        except (OSError,ValueError):
            result={'removed':0,'failed':['cleanup']}
        self.screenshot_cleanup_due=bool(result['failed'])
        self.next_screenshot_cleanup=time.monotonic()+(60 if result['failed'] else 0)
        if result['failed']:self.status.set('Some screenshots could not be removed; cleanup will retry.')
        return result

    def save_screenshot_setting(self):
        try:
            self.ledger.configure(screenshot_runs=self.integer(self.setting_vars['screenshot_runs'].get()))
            self.screenshot_cleanup_due=True
            self.cleanup_screenshots()
            self.status.set('Screenshot retention saved')
        except ValueError as exc:messagebox.showerror(tr('Check settings'),tr(str(exc)))

    @staticmethod
    def duration(minutes):
        minutes = math.ceil(minutes)
        hours, remaining = divmod(minutes, 60)
        return f'{hours:,}h {remaining:02d}m' if hours else f'{remaining} min'

    @staticmethod
    def integer(text):
        return parse_amount(text)

    def result_ready(self):
        if self.auto_busy or self.auto_pending or self.busy_capture or self.pending_ocr:
            return False,'Reading capture · wait before saving'
        try:
            parse_points(self.fields['points'].get())
            if self.fields['money'].get().strip():parse_amount(self.fields['money'].get())
        except ValueError:return False,'Capture or enter valid points; correct loot if entered'
        return True,'Ready to save'

    def overlay_run_status(self):
        if self.sanctum.session.standalone:return ''
        active=bool(self.ledger.active_start())
        state='Run active' if active else 'No active run'
        if active and self.party_notice.get():state+=' · previous run unfinished'
        if active and not self.sanctum.session.map_confirmed:state+=' · waiting for map'
        values=[]
        for name,kind,parser in [('Loot','money',parse_amount),('Pts','points',parse_points)]:
            raw=self.fields[kind].get().strip()
            value='—'
            if raw:
                try:
                    number=parser(raw)
                    if kind=='money' and number>=1000000:value=f'{number/1000000:.2f}'.rstrip('0').rstrip('.')+'M'
                    elif kind=='money' and number>=1000:value=f'{number/1000:.1f}'.rstrip('0').rstrip('.')+'K'
                    else:value=f'{number:,}'
                except ValueError:value='?'
            if kind in self.pending_ocr:value='…'
            values.append(f'{name} {value}')
        ready,reason=self.result_ready()
        if ready:action=f'{self.shortcut_hint("save")} save' if self.shortcuts['save'] else 'save in tracker'
        elif self.auto_busy or self.auto_pending or self.busy_capture or self.pending_ocr:action='reading…'
        elif any(value.endswith('?') for value in values):action='check values'
        else:action=f'{self.shortcut_hint("capture")} capture'
        return state+'\n'+' · '.join(values+[action])

    def quick_save_run(self):
        ready,reason=self.result_ready()
        if not ready:
            self.status.set(reason)
            return False
        return self.save_run(quiet=True)

    def save_run(self,quiet=False):
        if self.auto_busy or self.auto_pending or self.busy_capture or self.pending_ocr:
            self.status.set('Still reading your screenshot. Save when the readings are ready.')
            return
        try:
            active = self.ledger.active_start()
            included = self.already_included.get()
            lifetime = self.integer(self.fields['lifetime'].get()) if self.fields['lifetime'].get().strip() else None
            points = parse_points(self.fields['points'].get())
            failed = self.failed_run.get() or points < 0
            if failed:
                points = -abs(points)
            self.ledger.record_run(points=points, failed=failed,
                money=self.integer(self.fields['money'].get()) if self.fields['money'].get().strip() else None,
                day=self.run_day.get(), notes=self.notes.get(),
                consumes_ticket=self.consumes.get(), money_image=self.draft_images.get('money',''),
                points_image=self.draft_images.get('points',''), applied=not included,
                start_id=active['id'] if active and not included else None)
            if not included and lifetime is not None and self.ledger.summary()['lifetime_points'] != lifetime:
                self.ledger.correct_stats(lifetime_points=lifetime, reason='Lifetime total on run results')
            if self.sanctum.session.standalone:self.sanctum.stop_map_only()
            self.clear_draft(confirm=False)
            self.refresh()
            self.cleanup_screenshots()
            self.status.set(f'Failed run saved · {points} points · excluded from successful-run average' if failed else
                            'Run saved · loot value recorded separately from cash · ready for the next start')
            return True
        except Exception as exc:
            if quiet:self.status.set('Cannot save run: '+str(exc))
            else:messagebox.showerror(tr('Check run'), tr(str(exc)))
            return False

    def can_start_capture(self):
        if self.ledger.active_start():
            self.status.set('Your run is already active. Use Resume map in the Map tab, or save the results when finished.')
            return False
        if any(self.fields[k].get().strip() for k in ('money','points')) or any(k in self.draft_images for k in ('money','points')):
            self.status.set('Save or clear the previous result draft before starting the next run.')
            return False
        return True

    def begin_run(self,without_balance=None,manual=False):
        if not self.can_start_capture():
            return
        try:
            previous=self.capture_context()
            if without_balance is None:without_balance=not self.fields['balance'].get().strip()
            balance = None if without_balance else self.integer(self.fields['balance'].get())
            approximate = False if without_balance else self.balance_approximate or bool(re.search(r'[KkMmBb]', self.fields['balance'].get()))
            self.ledger.start_run(balance, '' if without_balance or manual else self.draft_images.get('balance',''), approximate)
            if manual:self.draft_images.pop('balance',None)
            if without_balance:
                self.fields['balance'].set('')
                self.draft_images.pop('balance',None)
            self.run_day.set(str(self.ledger.game_day()))
            self.persist_draft()
            self.refresh()
            if not manual:self.transfer_pending_captures(previous)
            self.status.set(('Run started without balance · wallet unchanged · open the game map inside Chaos to track' if without_balance else
                f'Run started · inventory balance {balance:,} · capture loot and points at the end'))
        except Exception as exc:
            self.status.set(f'Check start balance: {exc}')

    def cancel_run_start(self):
        if self.ledger.active_start() and messagebox.askyesno(tr('Cancel start'), tr('Cancel this run start? The observed balance stays recorded; no ticket has been consumed.')):
            self.ledger.cancel_start()
            self.clear_draft(confirm=False)
            self.refresh()

    def correct_stats_dialog(self):
        state = self.ledger.summary()
        window = tk.Toplevel(self)
        window.title('Correct current stats')
        frame = ttk.Frame(window, padding=22)
        frame.pack(fill='both', expand=True)
        ttk.Label(frame, text='Enter what the game shows NOW.', font=('Segoe UI Semibold',14)).pack(anchor='w')
        ttk.Label(frame, text='History stays saved. Older runs and purchases are already included in these totals.',
                  style='Muted.TLabel', wraplength=510).pack(anchor='w', pady=(5,12))
        values = {}
        self.stats_editor=window
        window.fields=values
        initial = dict(rank=str(state['eggs']) if state['is_emperor'] else '0', rank_points=str(state['rank_points']) if state['is_emperor'] else '0', tickets=str(state['tickets']),
                       coins=f"{state['coins']:,}", lifetime_points='' if state['lifetime_points'] is None else str(state['lifetime_points']))
        for key, title in [('lifetime_points','Total Egg Heist points'),('tickets','Current tickets'),('coins','Actual current coin balance')]:
            ttk.Label(frame, text=title, style='Muted.TLabel').pack(anchor='w', pady=(5,2))
            values[key] = tk.StringVar(value=initial[key])
            ttk.Entry(frame, textvariable=values[key], width=42).pack(fill='x')
            if key=='coins':
                from balance_history import balance_preview
                window.balance_preview=tk.StringVar(value=balance_preview(values[key].get()))
                ttk.Label(frame,textvariable=window.balance_preview,foreground=ACCENT).pack(anchor='w',pady=(4,2))
                values[key].trace_add('write',lambda *_:window.balance_preview.set(balance_preview(values['coins'].get())))
        window.progress_preview=tk.StringVar()
        ttk.Label(frame,textvariable=window.progress_preview,foreground=ACCENT,wraplength=510).pack(anchor='w',pady=(10,6))
        ttk.Label(frame,text='Use the cumulative total on the points screen, not the +points earned in one run.',style='Muted.TLabel',wraplength=510).pack(anchor='w',pady=(0,8))
        advanced=self.disclosure(frame,'Advanced · calibrate eggs')
        window.calibrate=tk.BooleanVar(value=False)
        ttk.Checkbutton(advanced,text='Calibrate using the eggs shown in game',variable=window.calibrate).pack(anchor='w',pady=(0,8))
        calibration_entries=[]
        for key,title in [('rank','Egg Emperor eggs'),('rank_points','Points into the next egg (0–179)')]:
            ttk.Label(advanced,text=title,style='Muted.TLabel').pack(anchor='w',pady=(4,2))
            values[key]=tk.StringVar(value=initial[key])
            entry=ttk.Entry(advanced,textvariable=values[key],width=42,state='disabled');entry.pack(fill='x')
            calibration_entries.append(entry)
        ttk.Label(advanced,text='Optional: enter the total, egg count and progress from the same screen. This calibrates the Egg Emperor threshold.',style='Muted.TLabel',wraplength=510).pack(anchor='w',pady=8)
        def preview(*_):
            for entry in calibration_entries:entry.configure(state='normal' if window.calibrate.get() else 'disabled')
            try:
                total=self.integer(values['lifetime_points'].get())
                if total<0:raise ValueError()
                if window.calibrate.get():
                    threshold=total-self.integer(values['rank'].get())*self.ledger.settings()['points_per_rank']-self.integer(values['rank_points'].get())
                    text=f'Calibrated threshold: {threshold:,} total points'
                elif total<state['emperor_threshold']:text=f"{state['emperor_threshold']-total:,} points to Egg Emperor"
                else:
                    eggs,progress=divmod(total-state['emperor_threshold'],self.ledger.settings()['points_per_rank'])
                    text=f"Egg Emperor · {eggs:,} eggs · {progress}/{self.ledger.settings()['points_per_rank']}"
                window.progress_preview.set(text)
            except ValueError:window.progress_preview.set('Enter your cumulative total points to see progression.')
        for key in ('lifetime_points','rank','rank_points'):values[key].trace_add('write',preview)
        window.calibrate.trace_add('write',preview);preview()
        def save():
            try:
                changes = {key:self.integer(values[key].get()) for key in ('tickets','coins')
                           if values[key].get().strip() != initial[key]}
                if values['lifetime_points'].get().strip() != initial['lifetime_points'] and values['lifetime_points'].get().strip():
                    changes['lifetime_points'] = self.integer(values['lifetime_points'].get())
                if window.calibrate.get():
                    changes.update(lifetime_points=self.integer(values['lifetime_points'].get()),rank=self.integer(values['rank'].get()),rank_points=self.integer(values['rank_points'].get()))
                if not changes:
                    window.destroy()
                    return
                self.ledger.correct_stats(**changes, approximate=bool(re.search(r'[KkMmBb]',values['coins'].get()))
                    if 'coins' in changes else state['coins_approximate'])
                self.refresh()
                window.destroy()
                self.status.set('Current stats corrected · prior history preserved')
            except Exception as exc:
                messagebox.showerror(tr('Check current stats'), tr(str(exc)), parent=window)
        window.save_button=ttk.Button(frame, text='Apply current stats', command=save, style='Accent.TButton');window.save_button.pack(anchor='w',pady=(10,0))
        self.localizer.refresh(window)

    def show_balance_history(self):
        from balance_history import BalanceHistory
        self.balance_history=BalanceHistory(self)

    def log_spending(self):
        if not self.spend_amount.get().strip():
            self.status.set('No spending entered · leave blank if you bought nothing')
            return
        try:
            amount = self.integer(self.spend_amount.get())
            self.ledger.spend(amount, note=self.spend_note.get())
            self.spend_amount.set('')
            self.spend_note.set('')
            self.persist_draft()
            self.refresh()
            self.status.set(f'Spending logged · {amount:,} coins deducted')
        except Exception as exc:
            messagebox.showerror(tr('Check spending'), tr(str(exc)))

    def delete_expense(self):
        selected = self.spend_tree.selection()
        if selected and messagebox.askyesno(tr('Delete expense'), tr('Remove this spending entry and restore its coins?')):
            self.ledger.delete_spending(int(selected[0]))
            self.refresh()

    def export_spending(self):
        rows = self.ledger.spending()
        if not rows:
            messagebox.showinfo(tr('Export'), tr('No spending recorded yet.'))
            return
        path = filedialog.asksaveasfilename(defaultextension='.csv', initialfile='aniimo-spending.csv', filetypes=[(tr('CSV'),'*.csv')])
        if path:
            with open(path, 'w', newline='', encoding='utf-8-sig') as file:
                writer = csv.DictWriter(file, fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)
            self.status.set('Spending CSV exported')

    def buy_dialog(self):
        window = tk.Toplevel(self)
        window.title('Log actual ticket purchase')
        frame = ttk.Frame(window, padding=20)
        frame.pack()
        ttk.Label(frame, text='Tickets already bought today: ' + str(self.ledger.summary()['bought_today'])).pack()
        ttk.Label(frame, text='How many tickets did you buy?').pack(pady=8)
        count = tk.StringVar(value='15')
        ttk.Entry(frame, textvariable=count).pack()
        price = tk.StringVar()
        ttk.Label(frame, textvariable=price).pack(pady=10)
        def quote(*args):
            try:
                cost = ticket_cost(self.integer(count.get()), self.ledger.summary()['bought_today'], self.ledger.settings()['prices'])
                price.set(f'Expected shop cost: {cost:,} coins')
            except Exception:
                price.set('Enter a count within the remaining daily limit.')
        def save():
            try:
                cost = self.ledger.buy(self.integer(count.get()))
                self.refresh()
                window.destroy()
                self.status.set(f'Purchase logged · {cost:,} coins deducted from estimate')
            except Exception as exc:
                messagebox.showerror(tr('Check purchase'), tr(str(exc)), parent=window)
        count.trace_add('write', quote)
        quote()
        ttk.Button(frame, text='Log purchase', command=save).pack()

    def add_free_tickets(self,count,source='Chest reward',day=None):
        self.ledger.award_tickets(count,source,day)
        self.refresh()
        self.status.set(f'+{count} free tickets · wallet and daily shop count unchanged')

    def ticket_reward_dialog(self):
        window=tk.Toplevel(self);window.title('Add free tickets')
        frame=ttk.Frame(window,padding=20);frame.pack(fill='both',expand=True)
        ttk.Label(frame,text='Tickets from chests or rewards',font=('Segoe UI Semibold',14)).pack(anchor='w')
        ttk.Label(frame,text='Adds to your stock without spending coins or using paid shop slots.',style='Muted.TLabel').pack(anchor='w',pady=(4,12))
        count=tk.StringVar(value='1');source=tk.StringVar(value='Chest reward')
        ttk.Label(frame,text='Tickets received').pack(anchor='w')
        entry=ttk.Entry(frame,textvariable=count,width=18);entry.pack(anchor='w',pady=(3,8));entry.focus_set();entry.select_range(0,'end')
        ttk.Label(frame,text='Source / note (optional)').pack(anchor='w')
        ttk.Entry(frame,textvariable=source,width=50).pack(fill='x',pady=(3,10))
        def save():
            try:
                self.add_free_tickets(self.integer(count.get()),source.get())
                window.destroy()
            except Exception as exc:messagebox.showerror(tr('Check free tickets'),tr(str(exc)),parent=window)
        ttk.Button(frame,text='Add free tickets',style='Accent.TButton',command=save).pack(anchor='w')
        ttk.Label(frame,text='FREE TICKET HISTORY',style='Muted.TLabel').pack(anchor='w',pady=(16,5))
        tree=ttk.Treeview(frame,columns=('day','count','source'),show='headings',height=5)
        for key,label,width in [('day','Date',110),('count','Tickets',70),('source','Source',300)]:
            tree.heading(key,text=label);tree.column(key,width=width)
        tree.pack(fill='both',expand=True)
        for reward in self.ledger.ticket_rewards():
            tree.insert('','end',values=(reward['day'],f'+{reward["count"]}',reward['source']))

    def refresh_capture_targets(self):
        self.capture_targets=[dict(name='Aniimo window (automatic)',target='auto'),dict(name='Entire monitor (manual fallback)',target='monitor')]+game_windows()
        selected=self.ledger.settings()['capture_target']
        index=next((i for i,item in enumerate(self.capture_targets) if item['target']==selected),None)
        if index is None:
            index=len(self.capture_targets)
            self.capture_targets.append(dict(name='Selected game window unavailable · choose again',target=selected))
        self.capture_target_choice.configure(values=[item['name'] for item in self.capture_targets])
        self.capture_target_choice.current(index)

    def select_capture_target(self):
        if self.busy_capture or self.auto_busy or self.auto_pending or self.pending_ocr:
            self.refresh_capture_targets()
            self.status.set('Wait for the current capture to finish before changing capture target.')
            return
        index=self.capture_target_choice.current()
        if index<0:return
        target=self.capture_targets[index]['target']
        if target==self.ledger.settings()['capture_target']:return
        self.ledger.configure(capture_target=target,regions={},regions_space='monitor' if target=='monitor' else 'client')
        panel=self.sanctum
        panel.config.pop('minimap_region',None)
        panel.generation+=1;panel.context_serial+=1
        panel.session.map_confirmed=False
        panel.map_open=False;panel.map_rescan_pending=False
        panel.player=None;panel.position_time=0;panel.overlay_dirty=True
        panel.config.update(map_confirmed=False,player=None,reading={})
        panel.write_config()
        self.status.set('Capture target saved · open the game map to refresh. Custom reading areas were reset.')

    def save_settings(self):
        try:
            changes = {k: (v.get().strip() if k == 'deadline' else self.integer(v.get())) for k,v in self.setting_vars.items()}
            changes['prices'] = [self.integer(n) for n in self.price_var.get().split(',')]
            changes['budget_party']=self.budget_party.get()
            changes['monitor'] = self.monitor_choice.current()
            self.ledger.configure(**changes)
            self.refresh()
            self.cleanup_screenshots()
            self.status.set('Settings saved')
        except Exception as exc:
            messagebox.showerror(tr('Check settings'), tr(str(exc)))

    def selected(self):
        selected = self.tree.selection()
        return next((r for r in self.ledger.runs() if selected and r['id'] == int(selected[0])), None)

    def open_selected(self):
        row = self.selected()
        if row:
            found=False
            for key in ('money_image', 'points_image'):
                if row[key] and Path(row[key]).exists():
                    os.startfile(row[key])
                    found=True
            if not found:messagebox.showinfo(tr('Screenshots unavailable'),tr('No screenshots are available for this run. They were not captured or were removed by the retention limit.'))

    def edit_selected(self, event=None):
        if event is not None and event.type == tk.EventType.ButtonPress:
            item = self.tree.identify_row(event.y)
            if not item:
                return
            self.tree.selection_set(item)
        row = self.selected()
        if row is None:
            self.status.set('Select a saved run in Run history to edit it.')
            return
        existing = getattr(self, 'run_editor', None)
        if existing is not None and existing.winfo_exists():
            existing.lift()
            existing.focus_set()
            return
        window = self.run_editor = tk.Toplevel(self)
        window.title(f"Edit run #{row['id']}")
        window.transient(self)
        window.resizable(False, False)
        frame = ttk.Frame(window, padding=22)
        frame.pack(fill='both', expand=True)
        ttk.Label(frame, text=f"Edit saved run #{row['id']}", font=('Segoe UI Semibold', 15)).grid(
            row=0, column=0, columnspan=2, sticky='w', pady=(0, 5))
        ttk.Label(frame, text='Correct this result. Screenshots stay attached and your ongoing run stays open.',
                  style='Muted.TLabel', wraplength=500).grid(row=1, column=0, columnspan=2, sticky='w', pady=(0, 14))
        window.fields = {}
        for index, (key, label) in enumerate((('day', 'Game day (YYYY-MM-DD)'), ('points', 'Points gained / lost'),
                                              ('money', 'Loot value (blank = unknown)'),
                                              ('expenses', 'Run expenses (coins)'), ('notes', 'Notes')), start=2):
            ttk.Label(frame, text=label).grid(row=index, column=0, sticky='w', padx=(0, 18), pady=6)
            value = '' if row[key] is None else str(row[key])
            window.fields[key] = tk.StringVar(window, value=value)
            entry = ttk.Entry(frame, textvariable=window.fields[key], width=36)
            entry.grid(row=index, column=1, sticky='ew', pady=6)
            if key == 'points':
                entry.focus_set()
        window.consumes = tk.BooleanVar(window, value=bool(row['consumes_ticket']))
        window.failed = tk.BooleanVar(window, value=bool(row['failed']))
        window.included = tk.BooleanVar(window, value=not bool(row['applied']))
        ttk.Checkbutton(frame, text='Uses one ticket', variable=window.consumes).grid(
            row=7, column=0, sticky='w', pady=(8, 4))
        ttk.Checkbutton(frame, text='Failed run · enter points lost', variable=window.failed).grid(
            row=7, column=1, sticky='w', pady=(8, 4))
        ttk.Checkbutton(frame, text='Already included in current stats when logged', variable=window.included).grid(
            row=8, column=0, columnspan=2, sticky='w')
        corrections = self.ledger.corrections()
        checkpointed = bool(corrections and row['id'] <= corrections[0]['run_cutoff'])
        window.impact_text = tk.StringVar(window)
        def explain(*_):
            if checkpointed:
                text = 'A newer stat correction already includes this run. These edits change history only; current rank, tickets and balance stay unchanged.'
            elif window.included.get():
                text = 'This result is already included in your stats. Edits change history and averages without adding points or spending tickets again.'
            else:
                text = 'Saving recalculates current points, ticket use and run expenses. Loot value is separate from cash and never increases your balance.'
            window.impact_text.set(text)
        window.included.trace_add('write', explain)
        explain()
        ttk.Label(frame, textvariable=window.impact_text, style='Muted.TLabel', wraplength=500).grid(
            row=9, column=0, columnspan=2, sticky='w', pady=(14, 8))
        ttk.Label(frame, text='K / M amounts accepted. Expenses here are separate from between-run spending.',
                  style='Muted.TLabel', wraplength=500).grid(row=10, column=0, columnspan=2, sticky='w')
        actions = ttk.Frame(frame)
        actions.grid(row=11, column=0, columnspan=2, sticky='ew', pady=(18, 0))
        def save():
            try:
                values = window.fields
                points = parse_points(values['points'].get())
                failed = window.failed.get() or points < 0
                if failed:
                    points = -abs(points)
                self.ledger.update_run(row['id'], day=values['day'].get().strip(),
                    points=points, failed=failed,
                    money=self.integer(values['money'].get()) if values['money'].get().strip() else None,
                    expenses=self.integer(values['expenses'].get()), notes=values['notes'].get(),
                    consumes_ticket=window.consumes.get(), applied=not window.included.get())
                window.destroy()
                self.refresh()
                self.tree.selection_set(str(row['id']))
                self.tree.focus(str(row['id']))
                self.tree.see(str(row['id']))
                self.status.set(f"Run #{row['id']} updated · " +
                                ('history corrected; newer stat correction preserved' if checkpointed else 'totals refreshed'))
            except Exception as exc:
                messagebox.showerror(tr('Check run changes'), tr(str(exc)), parent=window)
        window.cancel_button = ttk.Button(actions, text='Cancel', command=window.destroy)
        window.cancel_button.pack(side='left')
        window.save_button = ttk.Button(actions, text='Save changes', command=save, style='Accent.TButton')
        window.save_button.pack(side='right')
        window.bind('<Escape>', lambda _: window.destroy())
        window.bind('<Control-Return>', lambda _: save())
        window.grab_set()

    def delete_selected(self):
        row = self.selected()
        if row and messagebox.askyesno(tr('Delete run'), tr(f"Delete run #{row['id']}? Progress counted since the latest stat correction will be undone. Observed balances stay recorded.")):
            self.ledger.delete_run(row['id'])
            self.refresh()

    def export(self):
        path = filedialog.asksaveasfilename(defaultextension='.csv', initialfile='aniimo-runs.csv', filetypes=[(tr('CSV'),'*.csv')])
        if path:
            rows = [{('loot_value' if key == 'money' else key):value for key,value in row.items()}
                    for row in self.ledger.runs()]
            if not rows:
                messagebox.showinfo(tr('Export'), tr('No runs recorded yet.'))
                return
            with open(path, 'w', newline='', encoding='utf-8-sig') as file:
                writer = csv.DictWriter(file, fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)
            self.status.set('CSV exported')

    def close(self):
        self.updates.close()
        self.after_cancel(self.tick_id)
        self.after_cancel(self.map_input_tick_id)
        self.sanctum.close()
        self.party.close()
        self.localizer.close()
        self.persist_draft()
        if self.hk:
            self.hk.close()
        self.destroy()


if __name__ == '__main__':
    if '--first-use-self-test' in sys.argv:
        # Isolated clean-install check. The caller must supply a disposable map
        # directory; this path never modifies the player's ledger or settings.
        import tempfile
        report_path=Path(sys.argv[sys.argv.index('--first-use-self-test')+1])
        try:
            if not os.environ.get('ANIIMO_MAP_ASSETS'):raise ValueError('Temporary map directory required')
            with tempfile.TemporaryDirectory() as directory:
                app=App(directory,hotkeys=False)
                app.ledger.configure(capture_target='monitor')
                assert not app.sanctum.assets_ready
                app.tutorial.first_use();app.update()
                assert app.tutorial.window is not None
                for index in (1,2,3):
                    app.tutorial.index=index;app.tutorial.show();app.update()
                    assert app.tutorial.image is not None
                app.tutorial.close();app.tutorial.first_use()
                assert app.tutorial.window is None
                app.tutorial.open();app.update();app.tutorial.close()
                app.sanctum.map_setup.download()
                deadline=time.monotonic()+240
                while app.sanctum.map_setup.busy and time.monotonic()<deadline:
                    app.update();time.sleep(.03)
                assert app.sanctum.assets_ready,app.sanctum.map_setup.label.cget('text')
                assert app.sanctum.maps.model(32).layout==32
                from unittest.mock import patch
                app.tabs.select(1);app.update()
                with patch('sanctum_panel.app_is_foreground',return_value=True),patch('sanctum_panel.game_is_foreground',return_value=False):
                    app.sanctum.opacity.set(45);app.sanctum.overlay_size.set(440)
                    app.sanctum.adjust_overlay();app.update()
                    assert app.sanctum.overlay.visible
                    assert abs(app.sanctum.overlay.window.attributes('-alpha')-.45)<.02
                    assert app.sanctum.overlay.window.winfo_width()==440
                    assert app.sanctum.engine is None and not app.sanctum.session.map_confirmed
                    app.tabs.select(2);app.sanctum.tick()
                    assert not app.sanctum.overlay.visible
                app.close()
            report_path.write_text(json.dumps(dict(ok=True,tutorial=True,first_use_once=True,reopen=True,map_download=True,overlay_preview=True)),encoding='utf-8')
        except Exception as exc:
            report_path.write_text(json.dumps(dict(ok=False,error=repr(exc))),encoding='utf-8')
        sys.exit()
    if '--sanctum-view' in sys.argv:
        from sanctum_view import run_viewer
        control = Path(sys.argv[sys.argv.index('--sanctum-view')+1])
        try:
            run_viewer(control,self_test='--viewer-self-test' in sys.argv)
        except Exception as exc:
            control.with_name('viewer-error.txt').write_text(str(exc),encoding='utf-8')
        sys.exit()
    if '--self-test' in sys.argv:
        import tempfile
        import sanctum_panel
        sanctum_panel.game_is_foreground=lambda:False
        from PIL import ImageDraw
        report_path = Path(sys.argv[sys.argv.index('--self-test') + 1])
        try:
            with tempfile.TemporaryDirectory() as temp:
                sample = Path(temp) / 'ocr.png'
                im = Image.new('RGB', (800, 200), 'white')
                ImageDraw.Draw(im).text((30, 30), 'Points earned: 360', fill='black', font_size=50)
                im.save(sample)
                ocr = recognize(sample)
                if '360' not in ocr:
                    raise RuntimeError('Packaged OCR could not recognize test number: ' + ocr)
                app = App(data_dir=temp, hotkeys=False)
                app.ledger.configure(capture_target='monitor')
                app.update()
                untouched=app.ledger.summary()
                app.sanctum.tracking_button.invoke()
                if not app.sanctum.session.standalone or app.ledger.active_start() or app.ledger.summary()!=untouched:
                    raise RuntimeError('Map-only mode changed the run ledger')
                app.sanctum.tracking_button.invoke()
                app.manual_start_button.invoke()
                if not app.ledger.active_start() or app.ledger.active_start()['balance'] is not None or app.ledger.summary()!=untouched:
                    raise RuntimeError('Balance-free start changed stats or invented a balance')
                app.ledger.cancel_start();app.clear_draft(confirm=False);app.refresh()
                points_only=Ledger(Path(temp)/'points-only.db')
                points_only.record_run(points=180)
                if points_only.runs()[0]['money'] is not None or points_only.summary()['tickets']!=104:
                    raise RuntimeError('Points-only result failed')
                points_only.award_tickets(3)
                if points_only.summary()['tickets']!=107 or points_only.summary()['coins']!=0 or points_only.summary()['bought_today']!=0:
                    raise RuntimeError('Free tickets changed the wallet or shop count')
                points_only.correct_stats(coins=1000000)
                if points_only.summary()['tickets']!=107 or points_only.buy(1)!=20000:
                    raise RuntimeError('Free-ticket reconciliation or paid shop tier failed')
                app.fields['balance'].set('1000000')
                app.begin_run()
                recovery_start=app.ledger.active_start()['id']
                app.sanctum.end_watch()
                app.sanctum.resume_watch()
                if not app.sanctum.session.watching or app.ledger.active_start()['id']!=recovery_start:
                    raise RuntimeError('Pause/resume did not preserve the active run')
                app.fields['money'].set('400000')
                app.fields['points'].set('360')
                app.save_run()
                app.spend_amount.set('80000')
                app.spend_note.set('Equipment for next run')
                app.log_spending()
                state = app.ledger.summary()
                if state['rank'] != 179 or state['tickets'] != 104 or state['coins'] != 920000:
                    raise RuntimeError('Packaged ledger result mismatch')
                from sanctum import Detector
                sample_map = Image.new('RGB',(800,600),(35,38,46))
                draw = ImageDraw.Draw(sample_map)
                draw.ellipse((190,290,210,310),outline='orange',width=4)
                draw.line((200,288,200,312),fill='white',width=2)
                draw.rectangle((490,290,510,310),outline='cyan',width=4)
                draw.line((488,300,512,300),fill='white',width=2)
                detector = Detector(Path(temp)/'vision-test')
                detector.calibrate(sample_map,(200,300),(500,300))
                vision = detector.detect(sample_map)
                if vision['candidates'] != [32]:
                    raise RuntimeError('Packaged map image recognition failed')
                from map_engine import MapEngine,MapLibrary
                from map_catalog import ALL_LAYOUTS
                for layout in ALL_LAYOUTS:
                    model=MapEngine(layout)
                    for entrance in (0,1):
                        route=model.route(entrance,2)
                        if (len([p for p in route['stops'] if p['k']=='key'])!=min(2,len(model.data['keyrooms'])) or
                            route['stops'][0]!=model.routes['pts'][entrance]):
                            raise RuntimeError('Missing local two-key entrance route for '+str(layout))
                    model.render((300,300))
                real_checks={}
                if '--vision-fixtures' in sys.argv:
                    folder=Path(sys.argv[sys.argv.index('--vision-fixtures')+1])
                    real=Detector(Path(temp)/'real-vision').detect(Image.open(folder/'actual-M-map.png'))
                    minimap=MapLibrary().identify(Image.open(folder/'actual-minimap.png'))
                    if real['candidates']!=[40] or not minimap or minimap['layout']!=37:
                        raise RuntimeError('Packaged real screenshot recognition failed')
                    real_checks=dict(real_map_layout=40,minimap_layout=37)
                    if (folder/'actual-M-map-32.png').exists():
                        horizontal=Detector(Path(temp)/'horizontal-vision').detect(Image.open(folder/'actual-M-map-32.png'))
                        if horizontal['candidates']!=[32]:
                            raise RuntimeError('Horizontal full-map entrances were not recognized')
                        if 'player' in horizontal and not (365<=horizontal['player'][0]<=435 and 505<=horizontal['player'][1]<=565):
                            raise RuntimeError('Horizontal map player matched fog instead of the arrow')
                        json.dumps(horizontal)
                        real_checks['horizontal_map_layout']=32
                    if (folder/'actual-M-map-39.png').exists():
                        newer=Detector(Path(temp)/'newer-vision').detect(Image.open(folder/'actual-M-map-39.png'))
                        if newer['candidates']!=[39]:raise RuntimeError('Newer full-map screenshot was not recognized')
                        if Detector(Path(temp)/'newer-vision').is_map_screen(Image.open(folder/'actual-inventory.png')):
                            raise RuntimeError('Inventory was accepted as a full map')
                        real_checks.update(newer_map_layout=39,full_map_interface_gate=True)
                    if (folder/'occluded-quarter.png').exists():
                        covered=Detector(Path(temp)/'covered-vision').detect(Image.open(folder/'occluded-quarter.png'))
                        if covered['candidates']!=[39] or covered.get('occluded_portals')!=['orange']:
                            raise RuntimeError('Partly covered entrance was not recovered')
                        json.dumps(covered)
                        real_checks['partial_portal_overlap']=True
                    if (folder/'player-on-blue-39.png').exists():
                        rim=Detector(Path(temp)/'rim-vision').detect(Image.open(folder/'player-on-blue-39.png'))
                        if rim['candidates']!=[39] or rim.get('occluded_portals')!=['blue']:
                            raise RuntimeError('Blue portal rim behind a player badge was not recovered')
                        real_checks['blue_portal_rim']=True
                    if (folder/'actual-inventory.png').exists():
                        def wait_capture(predicate):
                            until=time.monotonic()+25
                            while not predicate() and time.monotonic()<until:
                                app.update();time.sleep(.02)
                            if not predicate():raise RuntimeError('Automatic capture timed out: '+app.status.get())
                        app.auto_attach(folder/'actual-inventory.png')
                        wait_capture(lambda:app.ledger.active_start() is not None)
                        app.auto_attach(folder/'actual-loot.png')
                        app.auto_attach(folder/'actual-points.png')
                        wait_capture(lambda:app.fields['money'].get()=='431719' and app.fields['points'].get()=='192')
                        real_checks['automatic_capture']=True
                        if (folder/'actual-inventory-zero.png').exists():
                            app.ledger.cancel_start();app.clear_draft(confirm=False);app.refresh()
                            app.auto_attach(folder/'actual-inventory-zero.png')
                            wait_capture(lambda:app.ledger.active_start() is not None)
                            if app.ledger.active_start()['balance']!=7654000 or app.ledger.summary()['coins']!=7654000:
                                raise RuntimeError('Decimal-zero currency capture lost its K multiplier')
                            real_checks['decimal_zero_balance']=7654000
                budget=break_even({**app.ledger.settings(),'daily_tickets':18})
                if round(budget['per_run'])!=536032:
                    raise RuntimeError('Packaged break-even estimate failed')
                unchanged=app.ledger.summary()
                app.sanctum.difficulty.set('Hard');app.sanctum.change_difficulty()
                app.sanctum.route_goal.set('eggs');app.sanctum.egg_count.set('2')
                app.sanctum.icon_vars['trials'].set(False);app.sanctum.save_preferences()
                if app.ledger.summary()!=unchanged:raise RuntimeError('Map preferences changed progression')
                app.close();app=App(data_dir=temp,hotkeys=False)
                if app.sanctum.difficulty.get()!='Hard' or app.sanctum.route_goal.get()!='eggs' or app.sanctum.icon_vars['trials'].get():
                    raise RuntimeError('Map preferences were not restored')
                edit_active=app.ledger.active_start()
                edit_draft=app.ledger.draft()
                edit_id=app.ledger.runs()[0]['id']
                app.tree.selection_set(str(edit_id));app.edit_run_button.invoke()
                app.run_editor.fields['points'].set('400')
                app.run_editor.fields['money'].set('')
                app.run_editor.save_button.invoke()
                if (app.ledger.runs()[0]['id']!=edit_id or app.ledger.runs()[0]['points']!=400 or
                    app.ledger.runs()[0]['money'] is not None or app.ledger.active_start()!=edit_active or
                    app.ledger.draft()!=edit_draft):
                    raise RuntimeError('Packaged run editor failed or changed the active run/draft')
                real_checks['saved_run_editor']=True
                playtime_ledger=Ledger(Path(temp)/'playtime.db')
                playtime_ledger.configure(rank=990,normal_points=180,first_points=180,
                                         deadline='2026-10-29',extra_minutes=3)
                from datetime import date
                time_plan=forecast(playtime_ledger,date(2026,10,20))
                if (time_plan['play_minutes'],time_plan['session_minutes'],time_plan['daily_session_minutes'])!=(120,150,15):
                    raise RuntimeError('Packaged remaining-playtime forecast failed')
                if 'Estimated playtime' not in app.playtime_text.get() or app.setting_vars['run_minutes'].get()!='12':
                    raise RuntimeError('Packaged remaining-playtime display is missing')
                real_checks['remaining_playtime']=True
                before_failure=app.ledger.summary()
                app.failed_run.set(True);app.fields['points'].set('140');app.save_run()
                after_failure=app.ledger.summary()
                failed_row=app.ledger.runs()[0]
                if (failed_row['points']!=-140 or not failed_row['failed'] or
                    after_failure['rank']*180+after_failure['rank_points'] != before_failure['rank']*180+before_failure['rank_points']-140 or
                    after_failure['tickets']!=before_failure['tickets']-1 or
                    after_failure['normal']!=before_failure['normal'] or
                    app.tree.set(str(failed_row['id']),'result')!='Failed'):
                    raise RuntimeError('Packaged failed-run result or successful-only average failed')
                real_checks['failed_runs']=True
                if '--vision-fixtures' in sys.argv and (folder/'actual-loot-blank.png').exists():
                    unchanged=app.ledger.summary()
                    app.auto_attach(folder/'actual-loot-blank.png')
                    until=time.monotonic()+10
                    while app.fields['money'].get()!='420908' and time.monotonic()<until:
                        app.update();time.sleep(.02)
                    if app.fields['money'].get()!='420908' or app.ledger.summary()!=unchanged:
                        raise RuntimeError('Shifted loot screen was not recovered without changing stats')
                    real_checks['shifted_loot_value']=420908
                app.tabs.select(app.analytics_tab);app.analytics.period.set('All time');app.analytics.refresh();app.update()
                if app.analytics.report['totals']['failed']!=1 or app.analytics.report['totals']['average_points']!=before_failure['normal']:
                    raise RuntimeError('Packaged analytics miscounted failed runs or average points')
                if app.analytics.report['current_wallet']!=app.ledger.summary()['coins'] or len(app.analytics.charts)!=4:
                    raise RuntimeError('Packaged analytics wallet or charts failed')
                real_checks['analytics']=True
                app.clear_draft(confirm=False)
                if app.ledger.active_start():app.ledger.cancel_start();app.refresh()
                app.auto_messages.put((app.capture_context(),'unknown','unused.png','',{},None));app.tick()
                if not app.ledger.active_start() or 'waiting for map' not in app.overlay_run_status():
                    raise RuntimeError('Unrecognized capture did not start a waiting run')
                panel=app.sanctum
                panel.difficulty.set('Chaos');panel.change_difficulty()
                panel.overlay_size.set(350);panel.map_open=True;panel.map_rescan_pending=True;panel.busy=True
                panel.map_feedback='Identifying map…';panel.overlay_dirty=True
                old_foreground=sanctum_panel.game_is_foreground
                try:
                    sanctum_panel.game_is_foreground=lambda:True
                    panel.tick()
                    if not panel.overlay.visible or panel.overlay.window.winfo_height()>65:
                        raise RuntimeError('Open-map header was hidden or too large')
                    if real_checks.get('horizontal_map_layout')==32:
                        panel.accept_layout(32,horizontal);panel.map_rescan_pending=False;panel.tick()
                        shown=' '.join(panel.overlay.canvas.itemcget(i,'text') for i in panel.overlay.canvas.find_all() if panel.overlay.canvas.type(i)=='text')
                        if '32' not in shown or 'Map confirmed' not in shown:
                            raise RuntimeError('Map confirmation is not visible while M is open')
                    real_checks['open_map_header']=True
                finally:
                    sanctum_panel.game_is_foreground=old_foreground
                    panel.map_open=False;panel.map_rescan_pending=False;panel.busy=False;panel.tick()
                if app.quick_save_run():raise RuntimeError('Saved an empty run')
                app.fields['points'].set('180');app.pending_ocr.add('points')
                if app.quick_save_run():raise RuntimeError('Saved while reading points')
                app.pending_ocr.clear()
                if not app.quick_save_run() or app.ledger.active_start() or app.sanctum.overlay.visible:
                    raise RuntimeError('Points-only quick save failed to end/hide the run')
                if app.quick_save_run():raise RuntimeError('Duplicate empty quick save')
                if app.shortcut_specs['save']!=(120,6):raise RuntimeError('Default save shortcut missing')
                real_checks.update(both_entrance_routes=True,capture_header=True,unknown_capture_start=True,quick_save=True)
                if '--vision-fixtures' in sys.argv and (folder/'actual-points-positive-370.png').exists():
                    app.begin_run(without_balance=True)
                    app.ledger.configure(regions={**app.ledger.settings()['regions'],'points':[.8575,.5481481481481482,.9116666666666666,.597037037037037]})
                    app.failed_run.set(True)
                    app.auto_attach(folder/'actual-points-positive-370.png')
                    until=time.monotonic()+6
                    while time.monotonic()<until:
                        app.update();time.sleep(.01)
                        if app.fields['points'].get() and not app.pending_ocr and not app.auto_busy:break
                    if app.fields['points'].get()!='370' or app.failed_run.get():
                        raise RuntimeError('Successful +370 was read as a loss')
                    if not app.quick_save_run() or app.ledger.runs()[0]['points']!=370 or app.ledger.runs()[0]['failed']:
                        raise RuntimeError('Successful +370 was saved incorrectly')
                    real_checks['positive_points_370']=True
                app.begin_run(without_balance=True);app.fields['points'].set('192');app.notes.set('English note stays unchanged')
                language_state=app.ledger.summary();language_run=app.ledger.active_start()['id']
                app.set_language('pt-BR');app.update()
                if (app.save_run_button.cget('text')!='Salvar partida' or not app.capture_button.cget('text').startswith('Capturar tela') or
                    app.ledger.summary()!=language_state or app.ledger.active_start()['id']!=language_run or app.fields['points'].get()!='192'):
                    raise RuntimeError('Portuguese UI changed ledger data or did not translate')
                app.close();app=App(data_dir=temp,hotkeys=False);app.update()
                if (app.save_run_button.cget('text')!='Salvar partida' or app.fields['points'].get()!='192' or
                    app.notes.get()!='English note stays unchanged' or app.ledger.active_start()['id']!=language_run):
                    raise RuntimeError('Portuguese preference or active draft did not survive restart')
                app.set_language('en')
                if app.save_run_button.cget('text')!='Save run':raise RuntimeError('English language switch failed')
                real_checks['pt_br']=True
                retention_root=Path(temp)/'retention';retention_root.mkdir()
                retention_folder=retention_root/'screenshots';retention_folder.mkdir()
                retention_ledger=Ledger(retention_root/'tracker.db')
                retention_files=[]
                for index in range(31):
                    image=retention_folder/f'{index}.png';image.write_bytes(b'capture');retention_files.append(image)
                    retention_ledger.record_run(points=180,points_image=str(image),applied=False)
                retention_state=retention_ledger.summary()
                prune_screenshots(retention_ledger,retention_folder)
                if retention_files[0].exists() or not all(p.exists() for p in retention_files[1:]) or len(retention_ledger.runs())!=31:
                    raise RuntimeError('Default screenshot retention failed')
                retention_ledger.configure(screenshot_runs=0)
                draft_image=retention_folder/'draft.png';draft_image.write_bytes(b'draft')
                retention_ledger.save_draft({'images':{'points':str(draft_image)}})
                prune_screenshots(retention_ledger,retention_folder)
                if any(p.exists() for p in retention_files) or not draft_image.exists() or retention_ledger.summary()!=retention_state:
                    raise RuntimeError('Screenshot retention changed data or removed draft evidence')
                if app.setting_vars['screenshot_runs'].get()!='30':raise RuntimeError('Screenshot storage setting missing')
                real_checks['screenshot_retention']=True
                if '--party-server-test' in sys.argv:
                    party=app.party
                    party.mode.set('custom');party.address.set(sys.argv[sys.argv.index('--party-server-test')+1])
                    party.name.set('Packaged check');party.connect()
                    def party_wait(predicate):
                        deadline=time.monotonic()+10
                        while time.monotonic()<deadline:
                            app.update();time.sleep(.01)
                            if predicate():return
                        raise RuntimeError('Packaged party network check timed out: '+party.status.get())
                    party_wait(lambda:party.connected and party.state)
                    app.sanctum.session.enable(True);app.sanctum.session.resume()
                    party.observed_layout(32,dict(map_screen=True,candidates=[32],scores=dict(orange=.91,blue=.9)))
                    party_wait(lambda:party.state['layout']==32 and app.sanctum.engine is not None and app.sanctum.engine.layout==32)
                    party.difficulty.set('Hard');party.difficulty_changed()
                    party_wait(lambda:party.state['difficulty']=='Hard' and party.state['layout'] is None)
                    party.leave();real_checks['party_network']=True
                app.close()
                report_path.write_text(json.dumps(dict(ok=True, ocr=ocr, rank=state['rank'], tickets=state['tickets'], coins=state['coins'],vision_layout=32,local_layouts=len(ALL_LAYOUTS),map_preferences=True,solo_18_break_even=round(budget['per_run']),recovered_same_run=True,optional_start=True,map_only=True,points_only=True,free_tickets=True,**real_checks)), encoding='utf-8')
        except Exception as exc:
            report_path.write_text(json.dumps(dict(ok=False, error=repr(exc))), encoding='utf-8')
        sys.exit()
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        pass
    # Named mutex avoids two app copies sharing shortcuts and silently editing one draft.
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateMutexW.restype = ctypes.c_void_p
    mutex = kernel.CreateMutexW(None, False, 'Local\\AniimoEggheistTracker')
    if ctypes.get_last_error() == 183:
        ctypes.windll.user32.MessageBoxW(None, 'Aniimo Tracker is already open. Check your taskbar.', 'Aniimo Tracker', 0)
    else:
        App().mainloop()
