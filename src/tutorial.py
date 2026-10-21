"""Reopenable walkthrough. Only anonymized examples are shipped."""
import json
from pathlib import Path
import tkinter as tk
from tkinter import ttk
from PIL import Image,ImageTk

from asset_paths import BUNDLED
ASSETS=BUNDLED/'tutorial'


def tutorial_steps(shortcuts, portuguese=False):
    capture,save,overlay,map_key=(shortcuts(k) for k in ('capture','save','overlay','map'))
    if portuguese:
        return [
            ('Prepare em dois passos', '1 · Baixe o pacote de mapas pelo botão abaixo. É necessário para reconhecer layouts e mostrar a sobreposição. O download ocorre em segundo plano.\n\n2 · Informe seus dados atuais: total do Egg Heist, ingressos e saldo. Na tela de pontos, o total fica antes da barra /. Você pode digitá-lo agora, sem iniciar uma partida. Para usar só o mapa, os dados são opcionais.',None,None),
            ('1 · Comece pela mochila',f'Depois de vender itens e comprar equipamentos, abra esta tela e pressione {capture}. Sem uma partida ativa, a captura inicia a partida e lê o saldo no canto superior direito.\n\nO saldo é opcional: você também pode usar Iniciar partida sem preenchê-lo. Fora de uma tela reconhecida, a captura inicia sem saldo.','inventory.png',(.74,.025,.86,.10)),
            ('2 · Capture o saque',f'Na tela de resultado, pressione {capture} novamente. O aplicativo registra o valor do saque desta partida.\n\nEste valor não é dinheiro recebido: itens podem ficar no inventário ou ser vendidos por outro preço. O saldo real será atualizado na próxima captura da mochila.','loot.png',(.025,.30,.28,.45)),
            ('3 · Total e ganho são diferentes',f'52.530 é o TOTAL acumulado; +370 é o ganho DESTA PARTIDA. Capture com {capture}, confira o ganho e pressione {save} para salvar. O total lido permite conferir sua progressão.\n\nO x211 abaixo da medalha é a contagem de ovos do Imperador. O bônus diário já está incluído em +370. Só os pontos da partida são obrigatórios; saque é opcional e derrotas usam pontos negativos.','points.png',(.72,.55,.93,.62)),
            ('4 · Mapa durante a partida',f'Escolha a dificuldade em Mapa e rotas. Durante uma partida, abra o mapa do jogo com {map_key} para reconhecer o layout. A barra mostra a confirmação; o mapa da sobreposição fica oculto enquanto o mapa do jogo está aberto.\n\nUse {overlay} para alternar a sobreposição. Use Mover sobreposição para reposicioná-la e bloquear novamente. Também é possível iniciar só o rastreador de mapa.',None,None),
            ('5 · Confira a progressão', 'O aplicativo usa seus pontos TOTAIS, inclusive antes do Imperador dos Ovos. Por padrão, o Imperador começa em 14.550 pontos; depois são 180 pontos por ovo. Ovos e progresso são calculados automaticamente.\n\nJá no Imperador e a contagem não bate? Abra Informar dados atuais → Avançado · calibrar ovos e ative a calibração com os ovos do jogo. Informe juntos o total, os ovos e o progresso dentro do próximo ovo. Exemplo: 52.530 total, x211 ovos, 0/180. Não use +370 como total.',None,None),
            ('6 · Jogue em grupo', 'Na aba Grupo, salve seu nome e crie um grupo ou entre com o código de um amigo. O limite é de três pessoas. O anfitrião escolhe a dificuldade. Qualquer membro pode iniciar a próxima navegação compartilhada.\n\nCada jogador inicia sua partida ou seu rastreador. O melhor reconhecimento e as posições são compartilhados. Capturas e dados financeiros ficam no seu PC.',None,None),
            ('Tudo pronto', 'Você pode corrigir leituras antes de salvar e editar partidas pelo histórico. Ingressos comprados ou gratuitos ficam no cartão de ingressos. Análise mostra os gráficos.\n\nTodos os atalhos podem ser alterados em Configurações. Abra este guia novamente pelo botão ? no topo. As imagens deste guia são exemplos anonimizados.',None,None)]
    return [
        ('Set up in two steps', '1 · Download the map pack below. It enables layout recognition and the overlay. Installation runs in the background.\n\n2 · Set current stats: total Egg Heist points, tickets and balance. On the points-result screen, the total is the number before /. You can type it now, without starting a run. Stats are optional if you only want maps.',None,None),
        ('1 · Start from Inventory',f'After selling items and shopping, open this screen and press {capture}. With no active run, the capture starts a run and reads your balance at the top right.\n\nBalance is optional: you can also click Start run with the balance blank. Capturing an unrecognized screen starts a run without a balance.','inventory.png',(.74,.025,.86,.10)),
        ('2 · Capture the loot result',f'On the loot result screen, press {capture} again. The app records the value of the loot from this run.\n\nThis is not cash received: you may keep items or sell them for a different price. Your next Inventory capture updates the actual wallet checkpoint.','loot.png',(.025,.30,.28,.45)),
        ('3 · Total and award are different',f'52,530 is your cumulative TOTAL; +370 is THIS RUN’S award. Capture with {capture}, review the award, then press {save} to save. The detected total helps reconcile progression.\n\nThe x211 below the medal is your Emperor egg count. The daily bonus is already included in +370. Only run points are required; loot is optional and losses use negative points.','points.png',(.72,.55,.93,.62)),
        ('4 · Navigate during a run',f'Choose your difficulty in Map & routes. During a run, open the game map with {map_key} to identify the layout. The compact bar confirms recognition; the overlay map hides while the game map is open.\n\nPress {overlay} to toggle the overlay. Use Move overlay to reposition it, then lock it again. You can also start map-only tracking.',None,None),
        ('5 · Check your progression', 'The app uses your TOTAL points, including before Egg Emperor. The default Emperor threshold is 14,550; after that, each egg takes 180 points. Your eggs and within-egg progress are derived automatically.\n\nAlready Emperor, but the count differs? Open Set current stats → Advanced · calibrate eggs. Enable “Calibrate using the eggs shown in game” and enter total, eggs and progress into the next egg together. Example: 52,530 total, x211 eggs, 0/180. Do not enter +370 as the total.',None,None),
        ('6 · Play with a party', 'In Party, save your username and create a party or join a friend’s code. Up to three players can join. The host chooses difficulty. Any member can start the next shared navigation session.\n\nEach player starts their own run or map tracker. The strongest recognition and player positions are shared. Screenshots and financial data stay on your PC.',None,None),
        ('You’re ready', 'Correct readings before saving, or edit saved runs in Run history. Buy tickets and Free tickets are on the ticket card. Analytics contains the graphs.\n\nAll shortcuts can be changed in Settings. Reopen this guide anytime with the ? button at the top. Tutorial images are anonymized examples.',None,None)]


class Tutorial:
    def __init__(self,app):
        self.app=app;self.path=app.data_dir/'tutorial-state.json';self.window=None;self.index=0;self.status_timer=None

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
        setup=ttk.Frame(frame);setup.pack(fill='x',pady=(12,0))
        self.download_button=ttk.Button(setup,text='Baixar pacote de mapas' if self.pt else 'Download map pack',command=self.download_maps)
        self.download_button.pack(side='left')
        self.stats_button=ttk.Button(setup,text='Informar dados atuais' if self.pt else 'Set current stats',command=self.setup_stats)
        self.stats_button.pack(side='left',padx=(10,0))
        self.setup_status=tk.StringVar()
        ttk.Label(frame,textvariable=self.setup_status,style='Muted.TLabel',wraplength=width-60).pack(anchor='w',pady=(6,0))
        self.canvas=tk.Canvas(frame,bg='#101a2b',highlightthickness=0);self.canvas.pack(fill='both',expand=True,pady=16)
        self.canvas.bind('<Configure>',lambda e:self.paint())
        row=ttk.Frame(frame);row.pack(fill='x')
        ttk.Button(row,text='Fechar guia' if self.pt else 'Close tutorial',command=self.close).pack(side='left')
        self.next=ttk.Button(row,style='Accent.TButton',command=self.advance);self.next.pack(side='right')
        self.back=ttk.Button(row,text='Voltar' if self.pt else 'Back',command=self.previous);self.back.pack(side='right',padx=8)
        frame.bind('<Configure>',lambda e:self.copy.configure(wraplength=max(500,e.width-48)))
        win.protocol('WM_DELETE_WINDOW',self.close);self.show();self.update_setup()
        win.bind('<Destroy>',self.destroyed,add='+')

    def destroyed(self,event):
        if event.widget is self.window:
            if self.status_timer is not None:self.app.after_cancel(self.status_timer)
            self.status_timer=None;self.window=None;self.image=None;self.photo=None

    def setup_stats(self):
        editor=getattr(self.app,'stats_editor',None)
        if editor is None or not editor.winfo_exists():self.app.correct_stats_dialog()
        self.app.stats_editor.transient(self.window)
        self.app.stats_editor.lift()

    def download_maps(self):
        self.app.tabs.select(self.app.sanctum_tab)
        setup=self.app.sanctum.map_setup
        if not self.app.sanctum.assets_ready and not setup.busy:setup.download()
        self.update_setup(schedule=False)

    def update_setup(self,schedule=True):
        if not self.window or not self.window.winfo_exists():return
        setup=self.app.sanctum.map_setup
        ready=self.app.sanctum.assets_ready
        state=self.app.ledger.summary()
        if self.pt:
            maps='Instalados' if ready else 'Baixando…' if setup.busy else 'Não instalados'
            total='informe seus pontos' if state['lifetime_points'] is None else f"{state['lifetime_points']:,}".replace(',','.')+' pontos'
            text=f'Mapas: {maps} · Seus dados: {total} · {state["tickets"]} ingressos'
        else:
            maps='Installed' if ready else 'Downloading…' if setup.busy else 'Not installed'
            total='set your points' if state['lifetime_points'] is None else f"{state['lifetime_points']:,} points"
            text=f'Maps: {maps} · Your stats: {total} · {state["tickets"]} tickets'
        self.setup_status.set(text)
        self.download_button.configure(state='disabled' if ready or setup.busy else 'normal')
        if schedule:self.status_timer=self.app.after(700,self.update_setup)

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
        if self.index==3:
            labels=('TOTAL','GANHO DA PARTIDA','OVOS DO IMPERADOR') if self.pt else ('TOTAL','RUN AWARD','EMPEROR EGGS')
            for (a,b,c,d),label,color in zip(((.72,.56,.764,.596),(.842,.56,.908,.596),(.473,.73,.543,.79)),labels,('#79ffce','#ffdc75','#9fc3ff')):
                self.canvas.create_rectangle(x+a*image.width,y+b*image.height,x+c*image.width,y+d*image.height,outline=color,width=3,tags='annotation')
                text=self.canvas.create_text(x+a*image.width,y+b*image.height-5,text=label,anchor='sw',fill=color,font=('Segoe UI Semibold',9),tags='annotation')
                box=self.canvas.bbox(text)
                background=self.canvas.create_rectangle(box[0]-3,box[1]-2,box[2]+3,box[3]+2,fill='#101a2b',outline='',tags='annotation')
                self.canvas.tag_lower(background,text)
        elif self.focus:
            a,b,c,d=self.focus
            self.canvas.create_rectangle(x+a*image.width,y+b*image.height,x+c*image.width,y+d*image.height,outline='#79ffce',width=3)

    def advance(self):
        if self.index==len(self.steps)-1:self.close()
        else:self.index+=1;self.show()

    def previous(self):
        self.index=max(0,self.index-1);self.show()

    def close(self):
        if self.status_timer is not None:
            self.app.after_cancel(self.status_timer);self.status_timer=None
        try:self.path.write_text(json.dumps({'seen':True}),encoding='utf-8')
        except OSError:pass
        if self.window:self.window.destroy();self.window=None
        self.image=None;self.photo=None
