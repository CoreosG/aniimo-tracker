"""Compact cash-planning presentation; the ledger owns all budget calculations."""
import tkinter as tk
from tkinter import ttk


class BudgetPanel(ttk.Frame):
    COLORS = {'tickets': '#7f9fe8', 'keys': '#ddb879', 'gear': '#79dcc8'}

    def __init__(self, parent, open_settings):
        super().__init__(parent, style='Panel.TFrame', padding=14)
        heading = ttk.Frame(self, style='Panel.TFrame')
        heading.pack(fill='x')
        ttk.Label(heading, text='BREAK-EVEN ESTIMATE', style='Panel.TLabel',
                  foreground='#98aac3', font=('Segoe UI Semibold', 9)).pack(side='left')
        self.settings_button = ttk.Button(heading, text='Adjust budget',
                                          style='Card.TButton', command=open_settings)
        self.settings_button.pack(side='right')
        target_row = ttk.Frame(self, style='Panel.TFrame')
        target_row.pack(fill='x', pady=(4, 0))
        self.target = tk.StringVar()
        ttk.Label(target_row, textvariable=self.target, style='Big.TLabel').pack(side='left')
        ttk.Label(target_row, text='coins to sell per run', style='Panel.TLabel',
                  foreground='#98aac3').pack(side='left', padx=(10, 0), pady=(7, 0))
        self.context = tk.StringVar()
        ttk.Label(self, textvariable=self.context, style='Panel.TLabel', foreground='#98aac3').pack(anchor='w', pady=(0, 9))
        self.bar = tk.Canvas(self, height=7, background='#263a53', highlightthickness=0)
        self.bar.pack(fill='x')
        self.bar.bind('<Configure>', lambda event: self._paint())
        self.amounts = {}
        self.parts = {}
        parts_row = ttk.Frame(self, style='Panel.TFrame')
        parts_row.pack(fill='x', pady=(8, 0))
        for index, (key, title) in enumerate((('tickets', 'Tickets'), ('keys', 'Keys'), ('gear', 'Gear'))):
            parts_row.columnconfigure(index, weight=1, uniform='parts')
            part = ttk.Frame(parts_row, style='Panel.TFrame')
            part.grid(row=0, column=index, sticky='ew')
            ttk.Label(part, text=title, style='Panel.TLabel', foreground=self.COLORS[key]).pack(anchor='w')
            self.parts[key] = tk.StringVar()
            ttk.Label(part, textvariable=self.parts[key], style='Panel.TLabel',
                      font=('Segoe UI Semibold', 12)).pack(anchor='w')
        self.detail_button = ttk.Button(self, text='Planning assumptions ▸',
                                        style='Card.TButton', command=self.toggle_details)
        self.detail_button.pack(anchor='w', pady=(10, 0))
        self.details = tk.StringVar()
        self.detail_label = ttk.Label(self, textvariable=self.details, style='Panel.TLabel',
                                     foreground='#98aac3', justify='left', wraplength=650)
        self.bind('<Configure>', lambda event: self.detail_label.configure(wraplength=max(240, event.width - 28)))

    def toggle_details(self):
        if self.detail_label.winfo_manager():
            self.detail_label.pack_forget()
            self.detail_button.configure(text='Planning assumptions ▸')
        else:
            self.detail_label.pack(anchor='w', fill='x', pady=(8, 0))
            self.detail_button.configure(text='Planning assumptions ▾')

    def update_budget(self, settings, budget):
        self.target.set(f"{budget['per_run']:,.0f}" if budget['per_run'] is not None else '—')
        self.context.set(('Party' if settings['budget_party'] else 'Solo') +
                         f" · {budget['weekly_runs']} runs/week · {settings['daily_tickets']} tickets/day")
        self.amounts = {'tickets': budget['tickets_per_run'], 'keys': budget['keys_per_run'],
                        'gear': budget['gear_per_run']}
        if budget['per_run'] is None:
            self.amounts = dict.fromkeys(self.amounts, 0)
        for key, value in self.amounts.items():
            self.parts[key].set(f'{value:,.0f}' if budget['per_run'] is not None else '—')
        self.details.set(
            f"Tickets bought every day: {budget['daily_tickets_cost']:,} coins/day.\n"
            f"Gear lasts {settings['gear_life']} runs; weekly discounts included.\n"
            f"Total budget: {budget['weekly_total']:,} coins/week.\n"
            'Sell enough loot to cover this target. Unsold loot is not cash.\n'
            'Planning only · no automatic wallet deductions.'
            if budget['per_run'] is not None else
            'No planned runs. Set tickets per day or runs per play day in Adjust budget.')
        self._paint()

    def _paint(self):
        self.bar.delete('all')
        total = sum(value or 0 for value in self.amounts.values())
        if not total:
            return
        left = 0
        width = self.bar.winfo_width()
        for key, value in self.amounts.items():
            right = left + width * (value or 0) / total
            self.bar.create_rectangle(left, 0, right, 7, fill=self.COLORS[key], outline='')
            left = right
