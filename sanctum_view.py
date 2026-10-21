"""Optional offline AniimoTools simulator windows, served on loopback only.

The main tracker renders its own preview/overlay using the local map/route data.
The original simulator controls remain available in these optional local windows.
No Python bridge or screenshot data are exposed to the simulator.
"""
import json
import time
import threading
from pathlib import Path
from sanctum import SITE_URL
from map_catalog import layouts_for


def route_script(config, entrance):
    data = dict(layout=config.get('layout') if config.get('layout') in layouts_for(config.get('difficulty','Chaos')) else None,
                keys=max(1,min(3,int(config.get('route_keys',2)))), entrance=int(entrance),
                reading=config.get('reading') or {},difficulty={'Beginner':3,'Hard':4,'Nightmare':5,'Chaos':6}[config.get('difficulty','Chaos')],goal=config.get('route_goal','keys'),icons=config.get('icons',{}))
    return r'''(() => {
      const c = CONFIG;
      if (location.hostname !== '127.0.0.1') return {ready:false,reason:'Outside local simulator'};
      let banner=document.getElementById('aniimo-tracker-status');
      if(!banner){banner=document.createElement('div');banner.id='aniimo-tracker-status';document.body.appendChild(banner);}
      banner.style.cssText='position:fixed;top:8px;right:12px;z-index:2147483000;background:#142d30;color:#baffde;padding:8px 12px;border:1px solid #68e1b9;border-radius:8px;font:13px sans-serif;pointer-events:none;max-width:430px';
      banner.textContent=c.layout ? 'Tracker: layout '+c.layout+' · '+c.keys+' key rooms · '+(c.entrance?'blue':'orange')+' entrance · player = last M reading' : 'Tracker: waiting for M-map detection / layout selection. Any map below is from the previous selection.';
      const choose = (selector,attr='aria-pressed') => {
        const b=document.querySelector(selector);
        if(!b) return false;
        if(b.getAttribute(attr)!=='true') { b.click(); return false; }
        return true;
      };
      if(!choose('[data-set-diff="'+c.difficulty+'"]','aria-checked')) return {ready:false,reason:'Selecting difficulty'};
      if(!c.layout) return {ready:false,reason:'Select a layout in the tracker or open M in game'};
      if(location.hash!=='#plan-'+c.layout || !document.querySelector('[data-view="route"]')) {
        const card=document.querySelector('.ls-card[data-plan="'+(20000+c.layout)+'"]') || document.querySelector('[data-open-plan="'+(20000+c.layout)+'"]');
        if(card) card.click();
        return {ready:false,reason:'Opening layout',hash:location.hash,card:!!card};
      }
      if(!choose('[data-view="route"]')) return {ready:false,reason:'Selecting suggested route'};
      if(!choose('[data-settings]')) return {ready:false,reason:'Opening route controls'};
      for(const goal of ['egg','key','rich','challenge']) {
        const b=document.querySelector('[data-goal="'+goal+'"]');
        if(!b) return {ready:false,reason:'Waiting for goals'};
        const wanted=(c.goal==='keys'&&goal==='key')||(c.goal==='eggs'&&goal==='egg')||(c.goal==='both'&&(goal==='egg'||goal==='key'));
        if((b.getAttribute('aria-pressed')==='true')!==wanted) {b.click(); return {ready:false,reason:'Selecting key-room goal'};}
      }
      for(const marker of document.querySelectorAll('.ls-mk')) {
        const category={key:'keys',nest:'eggs',challenge:'trials',room:'chests'}[marker.dataset.t];
        if(category)marker.style.display=c.icons[category]===false?'none':'';
      }
      const output=document.querySelector('.ls-stepper output');
      if(!output) return {ready:false,reason:'Waiting for key count'};
      const keys=Number(output.textContent);
      if(keys!==c.keys) {
        const b=document.querySelector('[data-k="'+(keys<c.keys?'1':'-1')+'"]');
        if(b&&!b.disabled){b.click();return {ready:false,reason:'Setting key count'};}
      }
      if(!choose('[data-start="'+c.entrance+'"]')) return {ready:false,reason:'Selecting entrance'};
      if(!choose('[data-end="near"]')) return {ready:false,reason:'Selecting nearest exit'};
      const a=document.querySelector('.ls-mk[data-t="door"][data-i="0"]');
      const b=document.querySelector('.ls-mk[data-t="door"][data-i="1"]');
      let dot=document.getElementById('aniimo-tracker-player');
      if(!c.reading.player || !c.reading.orange || !c.reading.blue){if(dot)dot.remove();}
      if(a&&b&&c.reading.player&&c.reading.orange&&c.reading.blue) {
        const layer=a.parentElement,w=layer.offsetWidth,h=layer.offsetHeight;
        const q1=[parseFloat(a.style.left)*w/100,parseFloat(a.style.top)*h/100];
        const q2=[parseFloat(b.style.left)*w/100,parseFloat(b.style.top)*h/100];
        const p1=c.reading.orange,p2=c.reading.blue,p=c.reading.player;
        const dx=p2[0]-p1[0],dy=p2[1]-p1[1],den=dx*dx+dy*dy;
        const ex=q2[0]-q1[0],ey=q2[1]-q1[1];
        if(den>400&&w>0&&h>0){
          const re=(ex*dx+ey*dy)/den,im=(ey*dx-ex*dy)/den;
          const x=q1[0]+re*(p[0]-p1[0])-im*(p[1]-p1[1]);
          const y=q1[1]+im*(p[0]-p1[0])+re*(p[1]-p1[1]);
          if(!dot){dot=document.createElement('div');dot.id='aniimo-tracker-player';layer.appendChild(dot);}
          dot.title='Player: last visible M-map reading';
          dot.style.cssText='position:absolute;width:14px;height:14px;background:#4cffba;border:3px solid white;border-radius:50%;box-shadow:0 0 0 4px #163c36;transform:translate(-50%,-50%);pointer-events:none;z-index:60;left:'+(x/w*100)+'%;top:'+(y/h*100)+'%';
        }
      }
      return {ready:true,layout:c.layout,keys:Number(output.textContent),entrance:c.entrance,player:!!document.getElementById('aniimo-tracker-player')};
    })()'''.replace('CONFIG',json.dumps(data))


def run_viewer(control_path, self_test=False):
    import webview
    from windows_capture import monitors
    from local_simulator import serve
    server,local_url=serve()
    control_path = Path(control_path).resolve()
    stopped = threading.Event()
    windows = []
    screens = monitors()
    target = next((s for s in screens if not s['primary']),screens[0])['bbox']
    width = max(620,min(950,(target[2]-target[0]-30)//2))
    height = min(920,target[3]-target[1]-60)
    for i,label in enumerate(('Orange','Blue')):
        window = webview.create_window(f'AniimoTools · {label} entrance · local simulator', local_url,
            width=width,height=height,x=target[0]+10+i*(width+10),y=target[1]+20,
            min_size=(620,500),background_color='#101b24',zoomable=True)
        windows.append(window)
    closed = set()
    for i,window in enumerate(windows):
        def on_close(index=i):
            closed.add(index)
            if len(closed)==len(windows):
                stopped.set()
        window.events.closed += on_close

    def drive():
        end = time.monotonic()+60 if self_test else None
        while not stopped.wait(.5):
            try:
                config = json.loads(control_path.read_text(encoding='utf-8'))
                if config.get('shutdown'):
                    break
                results = []
                for i,window in enumerate(windows):
                    if i in closed:
                        continue
                    result = window.evaluate_js(route_script(config,i))
                    results.append(result)
                status = dict(updated=time.time(),views=results)
                control_path.with_name('viewer-status.json').write_text(json.dumps(status),encoding='utf-8')
                if self_test and len(results)==2 and all(r and r.get('ready') for r in results):
                    control_path.with_name('viewer-test.json').write_text(json.dumps(dict(ok=True,views=results)),encoding='utf-8')
                    break
                if end and time.monotonic()>end:
                    raise RuntimeError('Simulator did not become ready within 60 seconds: '+str(results))
            except Exception as exc:
                control_path.with_name('viewer-error.txt').write_text(str(exc),encoding='utf-8')
                if end and time.monotonic()>end:
                    control_path.with_name('viewer-test.json').write_text(json.dumps(dict(ok=False,error=str(exc))),encoding='utf-8')
                    break
        for i,window in enumerate(windows):
            if i not in closed:
                try:
                    window.destroy()
                except Exception:
                    pass
    webview.settings['ALLOW_FILE_URLS'] = False
    webview.start(drive,gui='edgechromium',private_mode=False,storage_path=str(control_path.parent/'browser'))
    server.shutdown();server.server_close()
