"""Reopenable walkthrough. Only anonymized examples are shipped."""
import json
from pathlib import Path
import tkinter as tk
from tkinter import ttk
from PIL import Image,ImageTk

ASSETS=Path(__file__).with_name('assets')/'tutorial'


def tutorial_steps(shortcuts, portuguese=False):
    capture,save,overlay,map_key=(shortcuts(k) for k in ('capture','save','overlay','map'))
    if portuguese:
        return [
            ('Bem-vindo ao Eggheist', 'Uma captura reconhece a tela automaticamente. Este guia mostra quando capturar e o que será registrado.\n\nPrimeiro, use Corrigir dados para informar seus próprios pontos, ranque, ingressos e saldo. Em Mapa e rotas, baixe os mapas uma vez pelo botão do aplicativo.',None,None),
            ('1 · Comece pela mochila',f'Depois de vender itens e comprar equipamentos, abra esta tela e pressione {capture}. Sem uma partida ativa, a captura inicia a partida e lê o saldo no canto superior direito.\n\nO saldo é opcional: você também pode usar Iniciar partida sem preenchê-lo. Fora de uma tela reconhecida, a captura inicia sem saldo.','inventory.png',(.74,.025,.86,.10)),
            ('2 · Capture o saque',f'Na tela de resultado, pressione {capture} novamente. O aplicativo registra o valor do saque desta partida.\n\nEste valor não é dinheiro recebido: itens podem ficar no inventário ou ser vendidos por outro preço. O saldo real será atualizado na próxima captura da mochila.','loot.png',(.025,.30,.28,.45)),
            ('3 · Capture os pontos e salve',f'Na tela de pontos, pressione {capture}. Confira o ganho ou a perda no aplicativo ou na barra da sobreposição. Depois, pressione {save} para salvar.\n\nSó os pontos são obrigatórios. O saque é opcional. O bônus diário já está incluído no valor lido. Uma derrota deve aparecer com pontos negativos.','points.png',(.72,.55,.93,.62)),
            ('4 · Mapa durante a partida',f'Escolha a dificuldade em Mapa e rotas. Durante uma partida, abra o mapa do jogo com {map_key} para reconhecer o layout. A barra mostra a confirmação; o mapa da sobreposição fica oculto enquanto o mapa do jogo está aberto.\n\nUse {overlay} para alternar a sobreposição. Use Mover sobreposição para reposicioná-la e bloquear novamente. Também é possível iniciar só o rastreador de mapa.',None,None),
            ('5 · Jogue em grupo', 'Na aba Grupo, salve seu nome e crie um grupo ou entre com o código de um amigo. O limite é de três pessoas. O anfitrião escolhe a dificuldade e inicia a próxima navegação compartilhada.\n\nCada jogador precisa iniciar sua partida ou seu rastreador. O melhor reconhecimento é compartilhado, junto das posições. Capturas e dados financeiros ficam no seu PC.',None,None),
            ('Tudo pronto', 'Você pode corrigir leituras antes de salvar e editar partidas pelo histórico. Ingressos comprados ou gratuitos ficam no cartão de ingressos. Análise mostra os gráficos.\n\nTodos os atalhos podem ser alterados em Configurações. Abra este guia novamente pelo botão ? no topo. As imagens deste guia são exemplos anonimizados.',None,None)]
    return [
        ('Welcome to Eggheist', 'One capture shortcut recognizes the screen automatically. This guide shows when to capture and what gets recorded.\n\nFirst, use Correct stats to enter your own points, rank, tickets and balance. In Map & routes, download the maps once using the in-app button.',None,None),
        ('1 · Start from Inventory',f'After selling items and shopping, open this screen and press {capture}. With no active run, the capture starts a run and reads your balance at the top right.\n\nBalance is optional: you can also click Start run with the balance blank. Capturing an unrecognized screen starts a run without a balance.','inventory.png',(.74,.025,.86,.10)),
        ('2 · Capture the loot result',f'On the loot result screen, press {capture} again. The app records the value of the loot from this run.\n\nThis is not cash received: you may keep items or sell them for a different price. Your next Inventory capture updates the actual wallet checkpoint.','loot.png',(.025,.30,.28,.45)),
        ('3 · Capture points, then save',f'On the points result screen, press {capture}. Review the gain or loss in the app or the overlay bar. Then press {save} to save.\n\nOnly points are required; loot is optional. The daily bonus is already included in the reading. A failed run should have negative points.','points.png',(.72,.55,.93,.62)),
        ('4 · Navigate during a run',f'Choose your difficulty in Map & routes. During a run, open the game map with {map_key} to identify the layout. The compact bar confirms recognition; the overlay map hides while the game map is open.\n\nPress {overlay} to toggle the overlay. Use Move overlay to reposition it, then lock it again. You can also start map-only tracking.',None,None),
        ('5 · Play with a party', 'In Party, save your username and create a party or join a friend’s code. Up to three players can join. The host sets the difficulty and starts the next shared navigation session.\n\nEach player starts their own run or map tracker. The strongest map recognition and player positions are shared. Screenshots and financial data stay on your PC.',None,None),
        ('You’re ready', 'Correct readings before saving, or edit saved runs in Run history. Buy tickets and Free tickets are on the ticket card. Analytics contains the graphs.\n\nAll shortcuts can be changed in Settings. Reopen this guide anytime with the ? button at the top. Tutorial images are anonymized examples.',None,None)]


class Tutorial:
    def __init__(self,app):
        self.app=app;self.path=app.data_dir/'tutorial-state.json';self.window=None;self.index=0

    def first_use(self):
        try:seen=json.loads(self.path.read_text(encoding='utf-8')).get('seen',False)
        except (OSError,ValueError,AttributeError):seen=False
        if not seen:self.open()

    def open(self):
        if self.window and self.window.winfo_exists():self.window.lift();return
        self.pt=self.app.ledger.settings().get('language')=='pt-BR'
        self.steps=tutorial_steps(self.app.shortcut_hint,self.pt);self.index=0
        win=self.window=tk.Toplevel(self.app);win.title('Guia rápido' if self.pt else 'Quick tutorial')
        win.configure(bg='#0d1421');win.transient(self.app)
        width=min(1060,self.app.winfo_screenwidth()-90);height=min(820,self.app.winfo_screenheight()-100)
        win.geometry(f'{width}x{height}');win.minsize(760,580)
        frame=ttk.Frame(win,padding=24);frame.pack(fill='both',expand=True)
        self.progress=ttk.Label(frame,foreground='#79dcc8');self.progress.pack(anchor='w')
        self.title=ttk.Label(frame,font=('Segoe UI Semibold',23));self.title.pack(anchor='w',pady=(7,12))
        self.copy=ttk.Label(frame,justify='left',wraplength=width-60,font=('Segoe UI',11));self.copy.pack(fill='x')
        self.canvas=tk.Canvas(frame,bg='#101a2b',highlightthickness=0);self.canvas.pack(fill='both',expand=True,pady=16)
        self.canvas.bind('<Configure>',lambda e:self.paint())
        row=ttk.Frame(frame);row.pack(fill='x')
        ttk.Button(row,text='Fechar guia' if self.pt else 'Close tutorial',command=self.close).pack(side='left')
        self.next=ttk.Button(row,style='Accent.TButton',command=self.advance);self.next.pack(side='right')
        self.back=ttk.Button(row,text='Voltar' if self.pt else 'Back',command=self.previous);self.back.pack(side='right',padx=8)
        frame.bind('<Configure>',lambda e:self.copy.configure(wraplength=max(500,e.width-48)))
        win.protocol('WM_DELETE_WINDOW',self.close);self.show()

    def show(self):
        title,body,name,self.focus=self.steps[self.index]
        self.progress.configure(text=f'{self.index+1} / {len(self.steps)}')
        self.title.configure(text=title);self.copy.configure(text=body)
        self.back.configure(state='normal' if self.index else 'disabled')
        self.next.configure(text=('Concluir' if self.pt else 'Finish') if self.index==len(self.steps)-1 else ('Próximo' if self.pt else 'Next'))
        self.image=None
        if name:
            with Image.open(ASSETS/name) as im:self.image=im.convert('RGB')
        self.paint()

    def paint(self):
        self.canvas.delete('all');w,h=self.canvas.winfo_width(),self.canvas.winfo_height()
        if self.image is None:
            self.canvas.create_text(w/2,h/2,text='CAPTURAR  →  CONFERIR  →  SALVAR' if self.pt else 'CAPTURE  →  REVIEW  →  SAVE',fill='#79dcc8',font=('Segoe UI Semibold',18),width=max(100,w-40));return
        image=self.image.copy();image.thumbnail((max(1,w),max(1,h)))
        self.photo=ImageTk.PhotoImage(image);x,y=(w-image.width)/2,(h-image.height)/2
        self.canvas.create_image(x,y,image=self.photo,anchor='nw')
        if self.focus:
            a,b,c,d=self.focus
            self.canvas.create_rectangle(x+a*image.width,y+b*image.height,x+c*image.width,y+d*image.height,outline='#79ffce',width=3)

    def advance(self):
        if self.index==len(self.steps)-1:self.close()
        else:self.index+=1;self.show()

    def previous(self):
        self.index=max(0,self.index-1);self.show()

    def close(self):
        try:self.path.write_text(json.dumps({'seen':True}),encoding='utf-8')
        except OSError:pass
        if self.window:self.window.destroy();self.window=None
