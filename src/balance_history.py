"""Editable wallet observations with a readable amount preview."""
import tkinter as tk
from tkinter import ttk,messagebox
from readings import parse_amount
from i18n import tr


def balance_preview(text):
    try:
        amount=parse_amount(text)
        if amount<0:raise ValueError('Negative balance')
    except ValueError:return tr('Enter full coins or K/M, such as 7M or 7,654,000.')
    for divisor,suffix in ((1_000_000_000,'B'),(1_000_000,'M'),(1_000,'K')):
        if amount>=divisor:
            compact=f'{amount/divisor:.3f}'.rstrip('0').rstrip('.')+suffix;break
    else:compact=str(amount)
    return tr(f'{amount:,} coins · {compact}')


class BalanceHistory(tk.Toplevel):
    def __init__(self,app):
        super().__init__(app);self.app=app
        self.title(tr('Balance history'));self.geometry('1080x520');self.transient(app)
        frame=ttk.Frame(self,padding=18);frame.pack(fill='both',expand=True)
        ttk.Label(frame,text='Select an observation to correct its recorded balance.',font=('Segoe UI Semibold',13)).pack(anchor='w',pady=(0,12))
        table=ttk.Frame(frame);table.pack(fill='both',expand=True)
        self.tree=ttk.Treeview(table,columns=('time','rank','progress','tickets','coins','reason'),show='headings',selectmode='browse')
        for key,title,width in [('time','When',160),('rank','Rank',65),('progress','Progress',80),('tickets','Tickets',70),('coins','Balance',150),('reason','Source',300)]:
            self.tree.heading(key,text=tr(title));self.tree.column(key,width=width)
        scroll=ttk.Scrollbar(table,orient='vertical',command=self.tree.yview);self.tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right',fill='y');self.tree.pack(fill='both',expand=True)
        self.edit_button=ttk.Button(frame,text='Edit balance',command=self.edit,style='Accent.TButton');self.edit_button.pack(anchor='w',pady=(12,0))
        self.tree.bind('<Double-1>',lambda e:self.edit());self.reload()
        app.localizer.refresh(self)

    def reload(self):
        selection=self.tree.selection();self.tree.delete(*self.tree.get_children())
        self.rows={row['id']:row for row in self.app.ledger.corrections()}
        for row in self.rows.values():
            self.tree.insert('','end',iid=str(row['id']),values=(row['timestamp'],row['rank'],row['rank_points'],row['tickets'],
                tr(('≈ ' if row['approximate'] else '')+f"{row['coins']:,}"),tr(row['reason'])))
        selected=selection[0] if selection and int(selection[0]) in self.rows else str(next(iter(self.rows))) if self.rows else None
        if selected:self.tree.selection_set(selected)
        self.edit_button.configure(state='normal' if selected else 'disabled')

    def edit(self):
        selection=self.tree.selection()
        if not selection:return
        row=self.rows[int(selection[0])]
        window=self.editor=tk.Toplevel(self);window.title(tr('Edit balance'));window.transient(self)
        frame=ttk.Frame(window,padding=22);frame.pack(fill='both',expand=True)
        ttk.Label(frame,text=row['timestamp'],style='Muted.TLabel').pack(anchor='w')
        ttk.Label(frame,text='Recorded coin balance').pack(anchor='w',pady=(12,4))
        window.amount=tk.StringVar(value=f"{row['coins']:,}")
        entry=ttk.Entry(frame,textvariable=window.amount,width=45);entry.pack(fill='x')
        window.preview=tk.StringVar()
        ttk.Label(frame,textvariable=window.preview,foreground='#79dcc8').pack(anchor='w',pady=8)
        window.amount.trace_add('write',lambda *_:window.preview.set(balance_preview(window.amount.get())))
        window.preview.set(balance_preview(window.amount.get()))
        text='Latest checkpoint: current wallet will recalculate.' if row['id']==max(self.rows) else 'Historical checkpoint: newer balances stay unchanged.'
        ttk.Label(frame,text=text,wraplength=460,style='Muted.TLabel').pack(anchor='w',pady=(4,12))
        def save():
            try:
                text=window.amount.get();amount=parse_amount(text)
                self.app.ledger.update_balance_checkpoint(row['id'],amount,approximate=any(c in text.upper() for c in 'KMB'))
                self.app.refresh();self.reload();window.destroy();self.app.status.set('Balance checkpoint corrected · charts refreshed')
            except (ValueError,OSError) as exc:messagebox.showerror(tr('Check balance'),tr(str(exc)),parent=window)
        window.save_button=ttk.Button(frame,text='Save balance',style='Accent.TButton',command=save);window.save_button.pack(anchor='w')
        self.app.localizer.refresh(window);entry.focus_set()
