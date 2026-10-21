"""Presentation-only localization. Canonical variables and saved data stay intact."""
import re
import tkinter as tk
from tkinter import ttk
from pt_br import PT_BR

LANGUAGES={'en':'English','pt-BR':'Português (Brasil)'}
_language='en'
_pieces=sorted(PT_BR,key=len,reverse=True)
_pattern=re.compile('|'.join((r'(?<![\w])' if k[0].isalnum() else '')+re.escape(k)+(r'(?![\w])' if k[-1].isalnum() else '') for k in _pieces))

def set_language(language):
    global _language
    if language not in LANGUAGES:raise ValueError('Unsupported language')
    _language=language

def tr(text):
    text=str(text)
    if _language=='en' or not text:return text
    translated=PT_BR.get(text)
    if translated is None:translated=_pattern.sub(lambda m:PT_BR[m.group()],text)
    # Localized display only: numeric inputs and persisted values are untouched.
    translated=re.sub(r'(?<![\w])\d{1,3}(?:,\d{3})+(?:\.\d+)?|(?<![\w.])\d+\.\d+(?=[KMB\s%/·]|$)',
        lambda m:m[0].replace(',','\0').replace('.',',').replace('\0','.'),translated)
    translated=re.sub(r'(?<!\d)1 (derrotas|partidas|conhecidos|desconhecidos)\b',lambda m:'1 '+{'derrotas':'derrota','partidas':'partida','conhecidos':'conhecido','desconhecidos':'desconhecido'}[m[1]],translated)
    translated=re.sub(r'(?<!\d)(\d{4})-(\d{2})-(\d{2})(T?)',lambda m:f'{m[3]}/{m[2]}/{m[1]}'+(' ' if m[4] else ''),translated)
    return translated

def display_day(iso):
    return iso[8:10]+'/'+iso[5:7] if _language=='pt-BR' else iso[5:]


class Localizer:
    def __init__(self,root,language='en'):
        self.root=root;self.widgets={};self.variables={};self.texts={};self.traces=[];self.last_language=None
        set_language(language)
        root.bind_all('<Map>',self._mapped,add='+')

    def _mapped(self,event):
        self.attach(event.widget)

    def attach(self,widget):
        if widget in self.widgets:return
        self.widgets[widget]={}
        if isinstance(widget,(ttk.Label,ttk.Button,ttk.Checkbutton,ttk.Radiobutton,ttk.LabelFrame,tk.Label,tk.Button,tk.Checkbutton)):
            source=str(widget.cget('textvariable')) if 'textvariable' in widget.keys() else ''
            if source:self._mirror(widget,source)
        elif isinstance(widget,ttk.Combobox) and str(widget.cget('state'))=='readonly':
            source=str(widget.cget('textvariable'))
            if source:self._mirror(widget,source,editable=True)
        self._refresh_widget(widget)

    def _mirror(self,widget,source,editable=False):
        display=tk.StringVar(master=self.root)
        busy=[False]
        def update(*args):
            if busy[0]:return
            busy[0]=True
            try:display.set(tr(self.root.getvar(source)))
            finally:busy[0]=False
        command=self.root.register(update)
        self.root.tk.call('trace','add','variable',source,'write',command)
        self.traces.append((source,command))
        if editable:
            def choose(*args):
                if busy[0]:return
                raw=self.widgets[widget].get('values',('',()))[0]
                reverse={tr(value):value for value in raw}
                self.root.setvar(source,reverse.get(display.get(),display.get()))
            display.trace_add('write',choose)
        self.variables[widget]=(display,update)
        widget.configure(textvariable=display)
        update()

    def register_text(self,widget,raw,portuguese=None):
        self.texts[widget]=(raw,portuguese)

    def _option(self,widget,key,current,write):
        previous=self.widgets[widget].get(key)
        raw=previous[0] if previous and current==previous[1] else current
        value=tr(raw)
        if value!=current:write(value)
        self.widgets[widget][key]=(raw,value)

    def _refresh_widget(self,w):
        if isinstance(w,(tk.Tk,tk.Toplevel)):
            self._option(w,'title',w.title(),w.title)
        if 'text' in w.keys() and w not in self.variables:
            self._option(w,'text',str(w.cget('text')),lambda value:w.configure(text=value))
        if isinstance(w,ttk.Treeview):
            for column in w['columns']:
                self._option(w,'heading:'+column,w.heading(column,'text'),lambda value,c=column:w.heading(c,text=value))
            for item in w.get_children():
                values=list(w.item(item,'values'));changed=False
                for index,column in enumerate(w['columns']):
                    if column in ('result','included','money','day','amount','coins','timestamp') and index<len(values):
                        key='cell:'+item+':'+column
                        old=self.widgets[w].get(key)
                        raw=old[0] if old and values[index]==old[1] else values[index]
                        localized=tr(raw)
                        if localized!=values[index]:values[index]=localized;changed=True
                        self.widgets[w][key]=(raw,localized)
                if changed:w.item(item,values=values)
        if isinstance(w,ttk.Combobox) and str(w.cget('state'))=='readonly':
            current=tuple(w.cget('values'));old=self.widgets[w].get('values')
            raw=old[0] if old and current==old[1] else current
            values=tuple(tr(value) for value in raw)
            if current!=values:w.configure(values=values)
            self.widgets[w]['values']=(raw,values)
        if isinstance(w,ttk.Notebook):
            for tab in w.tabs():self._option(w,'tab:'+tab,w.tab(tab,'text'),lambda value,t=tab:w.tab(t,text=value))

    def refresh(self,root=None):
        if root is not None:
            self.attach(root)
            for child in root.winfo_children():self.refresh(child)
            return
        if _language=='en' and self.last_language=='en':return
        for w in list(self.widgets):
            if not w.winfo_exists():
                self.widgets.pop(w,None);self.variables.pop(w,None);self.texts.pop(w,None)
                continue
            self._refresh_widget(w)
        for display,update in self.variables.values():update()
        for w,(raw,portuguese) in list(self.texts.items()):
            if not w.winfo_exists():self.texts.pop(w,None);continue
            value=portuguese if _language=='pt-BR' and portuguese is not None else tr(raw)
            if w.get('1.0','end-1c')!=value:
                state=w.cget('state');w.configure(state='normal');w.delete('1.0','end');w.insert('1.0',value);w.configure(state=state)
        self.last_language=_language

    def close(self):
        for source,command in self.traces:
            try:self.root.tk.call('trace','remove','variable',source,'write',command)
            except tk.TclError:pass
