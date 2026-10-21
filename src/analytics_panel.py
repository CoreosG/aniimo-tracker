"""Native interactive history charts; no game observation or ledger writes."""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from datetime import datetime
from analytics import build_report, export_runs_csv
from i18n import tr,display_day

PANEL='#182235'
MUTED='#98aac3'
TEXT='#edf5f5'
TEAL='#79dcc8'
RED='#ff989c'
GOLD='#f4cc75'
BLUE='#8fbaff'


def compact(value):
    for divisor,suffix in ((1000000000,'B'),(1000000,'M'),(1000,'K')):
        if abs(value)>=divisor:
            return f'{value/divisor:.2f}'.rstrip('0').rstrip('.')+suffix
    return f'{value:,.0f}'


class HistoryChart(tk.Canvas):
    def create_text(self,*args,**kwargs):
        if 'text' in kwargs:kwargs['text']=tr(kwargs['text'])
        return super().create_text(*args,**kwargs)

    def __init__(self,parent,kind='bars',empty='No entries in this period'):
        super().__init__(parent,height=180,bg=PANEL,highlightthickness=0)
        self.kind,self.empty=kind,empty
        self.rows,self.series,self.positions=[],[],[]
        self.details=lambda row:''
        self.unknown=False
        self.bind('<Configure>',lambda event:self.draw())
        self.bind('<Motion>',self.hover)
        self.bind('<Leave>',lambda event:self.delete('hover'))

    def set_data(self,rows,series,details,unknown=False):
        self.rows,self.series,self.details,self.unknown=rows,series,details,unknown
        self.draw()

    def draw(self):
        self.delete('all')
        self.positions=[]
        width,height=max(200,self.winfo_width()),max(120,self.winfo_height())
        if not self.rows:
            self.create_text(width/2,height/2,text=self.empty,fill=MUTED,width=width-45,
                             font=('Segoe UI',10),justify='center')
            return
        left,top,right,bottom=53,15,width-16,height-28
        values=[row.get(key) for row in self.rows for key,label,color in self.series if row.get(key) is not None]
        low,high=min(values or [0]),max(values or [0])
        if self.kind=='bars':low,high=min(0,low),max(0,high)
        padding=max(1,(high-low)*.1)
        if low==high:padding=max(1,abs(low)*.08)
        low,high=low-padding,high+padding
        self.y=lambda value:bottom-(value-low)/(high-low)*(bottom-top)
        for value in (low,0 if low<0<high else (low+high)/2,high):
            y=self.y(value)
            self.create_line(left,y,right,y,fill='#2a394b')
            self.create_text(left-7,y,text=compact(value),anchor='e',fill=MUTED,font=('Segoe UI',8))
        if self.kind=='line':
            times=[datetime.fromisoformat(row['timestamp']).timestamp() for row in self.rows]
            span=max(times)-min(times)
            self.positions=[left+(value-min(times))/span*(right-left) if span else (left+right)/2 for value in times]
        else:
            step=(right-left)/len(self.rows)
            self.positions=[left+step*(index+.5) for index in range(len(self.rows))]
        if low<=0<=high:self.create_line(left,self.y(0),right,self.y(0),fill='#62718a')
        for series_index,(key,label,color) in enumerate(self.series):
            previous=None
            for index,row in enumerate(self.rows):
                value=row.get(key)
                if value is None:
                    previous=None
                    continue
                x,y=self.positions[index],self.y(value)
                if self.kind=='line':
                    if previous:self.create_line(*previous,x,y,fill=color,width=2)
                    fill=PANEL if row.get('estimated') else color
                    self.create_oval(x-4,y-4,x+4,y+4,fill=fill,outline=color,width=2)
                    previous=(x,y)
                else:
                    group=(right-left)/len(self.rows)
                    bar=max(.5,min(20,group*.78/len(self.series)))
                    x+= (series_index-(len(self.series)-1)/2)*bar
                    self.create_rectangle(x-bar*.44,self.y(0),x+bar*.44,y,fill=color,outline='')
        if self.unknown:
            for x,row in zip(self.positions,self.rows):
                if row.get('unknown_loot'):
                    self.create_text(x,bottom-7,text='?',fill=GOLD,font=('Segoe UI',9,'bold'))
        ticks=sorted(set((0,len(self.rows)//2,len(self.rows)-1)))
        same_day=self.kind=='line' and len({row['timestamp'][:10] for row in self.rows})==1
        for index in ticks:
            row=self.rows[index]
            label=row['timestamp'][11:16] if same_day else display_day(row.get('day') or row['timestamp'][:10])
            anchor='w' if index==0 else 'e' if index==len(self.rows)-1 else 'center'
            self.create_text(self.positions[index],bottom+16,text=label,fill=MUTED,anchor=anchor,font=('Segoe UI',8))

    def hover(self,event):
        self.delete('hover')
        if not self.rows or not self.positions:return
        def distance(index):
            x_distance=abs(self.positions[index]-event.x)
            if self.kind=='line':
                value=self.rows[index][self.series[0][0]]
                return x_distance+abs(self.y(value)-event.y)*.2
            return x_distance
        index=min(range(len(self.rows)),key=distance)
        x=self.positions[index]
        self.create_line(x,10,x,self.winfo_height()-25,fill=MUTED,dash=(3,3),tags='hover')
        label=self.create_text(10,10,text=self.details(self.rows[index]),anchor='nw',fill=TEXT,
                               width=min(280,max(150,self.winfo_width()-30)),font=('Segoe UI',9),tags='hover')
        box=self.bbox(label)
        position=min(max(8,event.x+12),self.winfo_width()-(box[2]-box[0])-12)
        self.move(label,position-10,4)
        box=self.bbox(label)
        background=self.create_rectangle(box[0]-6,box[1]-5,box[2]+6,box[3]+5,
                                          fill='#0d1421',outline='#55748a',tags='hover')
        self.tag_lower(background,label)


class AnalyticsPanel:
    def __init__(self,app,parent):
        self.app=app
        self.report=None
        scroll=ttk.Scrollbar(parent,orient='vertical')
        self.canvas=tk.Canvas(parent,bg='#0d1421',highlightthickness=0,yscrollcommand=scroll.set)
        scroll.configure(command=self.canvas.yview)
        scroll.pack(side='right',fill='y');self.canvas.pack(side='left',fill='both',expand=True)
        body=ttk.Frame(self.canvas)
        window=self.canvas.create_window(0,0,window=body,anchor='nw')
        body.bind('<Configure>',lambda event:self.canvas.configure(scrollregion=self.canvas.bbox('all')))
        self.canvas.bind('<Configure>',lambda event:self.canvas.itemconfigure(window,width=event.width))
        app.enable_wheel_scroll(self.canvas,body)
        heading=ttk.Frame(body);heading.pack(fill='x',pady=(0,5))
        ttk.Label(heading,text='Analytics',font=('Segoe UI Semibold',20)).pack(side='left')
        self.period=tk.StringVar(value='30 days')
        choice=ttk.Combobox(heading,textvariable=self.period,state='readonly',values=('Today','7 days','30 days','90 days','All time'),width=11)
        choice.pack(side='right',padx=(10,0));choice.bind('<<ComboboxSelected>>',lambda event:self.refresh())
        actions=ttk.Frame(body);actions.pack(fill='x',pady=(0,12))
        ttk.Label(actions,text='Loot value ≠ cash balance',style='Muted.TLabel').pack(side='left')
        ttk.Button(actions,text='Balance history / edit',command=app.show_balance_history).pack(side='right')
        self.export_button=ttk.Button(actions,text='Export this period',command=self.export)
        self.export_button.pack(side='right',padx=(0,8))
        metrics=ttk.Frame(body);metrics.pack(fill='x',pady=(0,14))
        self.metrics={}
        for index,(key,title) in enumerate((('loot','KNOWN LOOT'),('wallet','WALLET NOW'),('costs','LOGGED COSTS'),('runs','RUN RESULTS'))):
            metrics.columnconfigure(index,weight=1,uniform='analytics')
            box=ttk.Frame(metrics,style='Panel.TFrame',padding=12)
            box.grid(row=0,column=index,sticky='nsew',padx=(0 if not index else 8,0))
            ttk.Label(box,text=title,style='Panel.TLabel',foreground=MUTED,font=('Segoe UI',9)).pack(anchor='w')
            value,detail=tk.StringVar(),tk.StringVar()
            ttk.Label(box,textvariable=value,style='Panel.TLabel',font=('Segoe UI Semibold',22)).pack(anchor='w',pady=(4,2))
            label=ttk.Label(box,textvariable=detail,style='Panel.TLabel',foreground=MUTED,wraplength=210,font=('Segoe UI',9))
            label.pack(anchor='w')
            box.bind('<Configure>',lambda event,label=label:label.configure(wraplength=max(90,event.width-24)))
            self.metrics[key]=(value,detail)
        insights=ttk.Frame(body);insights.pack(fill='x',pady=(0,12))
        for index,(key,title) in enumerate((('hour','ESTIMATED LOOT / HOUR'),('margin','LOOT MINUS PLANNED COST'))):
            insights.columnconfigure(index,weight=1,uniform='insights')
            box=ttk.Frame(insights,style='Panel.TFrame',padding=12)
            box.grid(row=0,column=index,sticky='nsew',padx=(8 if index else 0,0))
            ttk.Label(box,text=title,style='Panel.TLabel',foreground=MUTED,font=('Segoe UI',9)).pack(anchor='w')
            value,detail=tk.StringVar(),tk.StringVar()
            ttk.Label(box,textvariable=value,style='Panel.TLabel',font=('Segoe UI Semibold',19)).pack(anchor='w')
            caption=ttk.Label(box,textvariable=detail,style='Panel.TLabel',foreground=MUTED,font=('Segoe UI',9),wraplength=400)
            caption.pack(anchor='w')
            box.bind('<Configure>',lambda event,label=caption:label.configure(wraplength=max(90,event.width-24)))
            self.metrics[key]=(value,detail)
        views=ttk.Notebook(body);views.pack(fill='both',expand=True,pady=(0,10))
        grid=ttk.Frame(views,padding=(0,10));views.add(grid,text='Charts')
        details=ttk.Frame(views,padding=(0,10));views.add(details,text='Run details')
        detail_bar=ttk.Frame(details);detail_bar.pack(fill='x',pady=(0,8))
        ttk.Label(detail_bar,text='Select a result to correct it. Unknown loot stays blank in CSV.',style='Muted.TLabel').pack(side='left')
        self.edit_button=ttk.Button(detail_bar,text='Edit selected run',command=self.edit_selected,state='disabled')
        self.edit_button.pack(side='right')
        self.results=ttk.Treeview(details,columns=('id','day','points','money','margin','result'),show='headings',height=13,selectmode='browse')
        for key,title,width in (('id','#',45),('day','Game day',110),('points','Points',80),('money','Loot value',110),
                                ('margin','Vs. planned cost',130),('result','Result',100)):
            self.results.heading(key,text=title,command=lambda column=key:self.sort_results(column))
            self.results.column(key,width=width,minwidth=40,anchor='w' if key in ('day','result') else 'e')
        self.results.tag_configure('failed',foreground=RED)
        table_scroll=ttk.Scrollbar(details,orient='vertical',command=self.results.yview)
        self.results.configure(yscrollcommand=table_scroll.set)
        table_scroll.pack(side='right',fill='y');self.results.pack(fill='both',expand=True)
        self.results.bind('<<TreeviewSelect>>',lambda event:self.edit_button.configure(state='normal' if self.results.selection() else 'disabled'))
        self.results.bind('<Double-1>',self.edit_selected);self.results.bind('<Return>',self.edit_selected)
        self.sort_column,self.sort_reverse='id',True
        ttk.Label(details,text='Planned cost uses your current budget settings. This comparison is not cash profit.',
                  style='Muted.TLabel',wraplength=750).pack(anchor='w',pady=(8,0))
        for column in (0,1):grid.columnconfigure(column,weight=1,uniform='charts')
        self.charts={}
        specs=(('loot','Loot & logged costs','Teal: known loot · red: logged costs · ?: missing loot'),
               ('wallet','Wallet history','Saved balance checkpoints · hollow dots: estimates'),
               ('points','Points per day','Teal: gained · red: lost · failures stay out of the average'),
               ('tickets','Ticket activity','Blue: bought · gold: free · red: used'))
        for index,(key,title,subtitle) in enumerate(specs):
            box=ttk.Frame(grid,style='Panel.TFrame',padding=12)
            box.grid(row=index//2,column=index%2,sticky='nsew',padx=(0 if not index%2 else 10,0),pady=(0,10))
            ttk.Label(box,text=title,style='Panel.TLabel',font=('Segoe UI Semibold',12)).pack(anchor='w')
            caption=ttk.Label(box,text=subtitle,style='Panel.TLabel',foreground=MUTED,font=('Segoe UI',8),wraplength=450)
            caption.pack(anchor='w',pady=(3,0))
            box.bind('<Configure>',lambda event,label=caption:label.configure(wraplength=max(120,event.width-24)))
            empty='Add a starting balance or use Correct stats to build wallet history' if key=='wallet' else 'No entries in this period'
            chart=HistoryChart(box,kind='line' if key=='wallet' else 'bars',empty=empty)
            chart.pack(fill='x',expand=True,pady=(4,0));self.charts[key]=chart
        self.range_text=tk.StringVar()
        ttk.Label(body,textvariable=self.range_text,style='Muted.TLabel',wraplength=1000).pack(anchor='w',pady=(0,5))
        ttk.Label(body,text='Hover a chart for exact values. Wallet changes include all sales and spending; they are not per-run profit.',
                  style='Muted.TLabel',wraplength=1000).pack(anchor='w')

    def refresh(self):
        days={'Today':1,'7 days':7,'30 days':30,'90 days':90,'All time':None}[self.period.get()]
        self.report=report=build_report(self.app.ledger,days)
        totals=report['totals'];known=totals['runs']-totals['unknown_loot']
        self.metrics['loot'][0].set('Unknown' if totals['runs'] and not known else compact(totals['loot']))
        self.metrics['loot'][1].set(f"{totals['loot']:,} recorded\n{known} known · {totals['unknown_loot']} unknown")
        self.metrics['wallet'][0].set(('≈ ' if report['wallet_approximate'] else '')+compact(report['current_wallet']) if report['wallet_known'] else '—')
        self.metrics['wallet'][1].set(('Current estimate' if report['wallet_estimated'] else 'Current recorded balance')+' · all time' if report['wallet_known'] else 'No balance checkpoint yet')
        self.metrics['costs'][0].set(compact(totals['costs']))
        self.metrics['costs'][1].set(f"{totals['costs']:,} coins\nTickets + run costs + spending")
        self.metrics['runs'][0].set(str(totals['runs']))
        average=f"{totals['average_points']:.1f} pts/success" if totals['average_points'] is not None else 'No successful pace yet'
        self.metrics['runs'][1].set(f"{totals['failed']} failed · {average}")
        performance=report['performance']
        self.metrics['hour'][0].set(compact(performance['loot_per_hour']) if performance['loot_per_hour'] is not None else '—')
        self.metrics['hour'][1].set(f"{performance['known_ticketed_loot']}/{performance['ticketed_runs']} ticketed runs with loot · {performance['minutes_per_run']} min/run incl. extras")
        margin=performance['average_modeled_margin']
        self.metrics['margin'][0].set(('+' if margin>=0 else '')+compact(margin)+'/run' if margin is not None else '—')
        budget=performance['planned_cost_per_run']
        self.metrics['margin'][1].set(f"Budget {compact(budget)}/run · item value, not cash profit" if budget is not None else 'Set planned runs in Settings to compare costs')
        self.export_button.configure(state='normal' if report['runs'] else 'disabled')
        self.render_results()
        rows=[{**row,'negative_costs':-row['costs'],'negative_lost':-row['lost'],'negative_used':-row['used']} for row in report['daily']]
        loot_rows=rows if any(row['runs'] or row['costs'] for row in rows) else []
        self.charts['loot'].set_data(loot_rows,(('loot','Loot',TEAL),('negative_costs','Costs',RED)),
            lambda row:f"{row['day']}\nKnown loot: {'Unknown' if row['loot'] is None else format(row['loot'],',')}\nLogged costs: {row['costs']:,}\n{row['unknown_loot']} run(s) with unknown loot",unknown=True)
        self.charts['wallet'].set_data(report['wallet'],(('coins','Wallet',BLUE),),
            lambda row:f"{row['timestamp'].replace('T',' ')}\n{'≈ ' if row['approximate'] else ''}{row['coins']:,} coins\n{row['reason']}"+('\nEstimated after logged costs' if row['estimated'] else ''))
        self.charts['points'].set_data(rows if totals['runs'] else [],(('gained','Gained',TEAL),('negative_lost','Lost',RED)),
            lambda row:f"{row['day']}\nGained: {row['gained']:,} · Lost: {row['lost']:,}\n{row['runs']} runs · {row['failed']} failed")
        self.charts['tickets'].set_data(rows if any(row['bought'] or row['free'] or row['used'] for row in rows) else [],
            (('bought','Bought',BLUE),('free','Free',GOLD),('negative_used','Used',RED)),
            lambda row:f"{row['day']}\nBought: {row['bought']} · Free: {row['free']}\nUsed: {row['used']}")
        change=f" · Wallet checkpoint change: {report['wallet_change']:+,} coins" if report['wallet_change'] is not None else ''
        self.range_text.set(f"{report['start']} → {report['end']} · Net points: {totals['net_points']:+,}"
            +f" · Estimated time: {performance['estimated_minutes']:,} min"+change)

    def render_results(self):
        selected=self.results.selection()
        rows=self.report['runs'] if self.report else []
        key={'margin':'modeled_margin','result':'failed','money':'money'}.get(self.sort_column,self.sort_column)
        # Missing loot is never sorted as a zero-valued run.
        known=sorted((row for row in rows if row[key] is not None),key=lambda row:row[key],reverse=self.sort_reverse)
        ordered=known+[row for row in rows if row[key] is None]
        self.results.delete(*self.results.get_children())
        for row in ordered:
            margin=row['modeled_margin']
            self.results.insert('','end',iid=str(row['id']),values=(row['id'],tr(row['day']),f"{row['points']:+,}",
                tr(f"{row['money']:,}") if row['money'] is not None else tr('Unknown'),
                tr(f"{margin:+,.0f}") if margin is not None else '—',
                tr('Failed' if row['failed'] else 'Success' if row['consumes_ticket'] else 'Bonus')),
                tags=('failed',) if row['failed'] else ())
        if selected and self.results.exists(selected[0]):self.results.selection_set(selected[0])
        self.edit_button.configure(state='normal' if self.results.selection() else 'disabled')

    def sort_results(self,column):
        self.sort_reverse=not self.sort_reverse if column==self.sort_column else False
        self.sort_column=column
        self.render_results()

    def edit_selected(self,event=None):
        if event is not None and event.type==tk.EventType.ButtonPress:
            item=self.results.identify_row(event.y)
            if not item:return
            self.results.selection_set(item)
        selected=self.results.selection()
        if not selected:return
        if self.app.tree.exists(selected[0]):
            self.app.tree.selection_set(selected[0])
            self.app.edit_selected()

    def export(self):
        if not self.report or not self.report['runs']:return
        path=filedialog.asksaveasfilename(parent=self.app,defaultextension='.csv',
            initialfile=f"aniimo-{self.report['start']}-{self.report['end']}.csv",
            filetypes=[(tr('CSV'),'*.csv')])
        if not path:return
        try:
            export_runs_csv(self.report,path)
            self.app.status.set(f"Exported {len(self.report['runs'])} run results")
        except OSError as error:
            messagebox.showerror(tr('Export failed'),str(error),parent=self.app)
