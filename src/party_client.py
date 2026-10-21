"""One background connection; UI and OCR never wait on the network."""
import json
import math
import queue
import random
import re
import threading
import time
from websockets.sync.client import connect
from map_catalog import layouts_for
from party_protocol import COLORS, VERSION, server_url, username


def read_state(state):
    if not isinstance(state, dict): raise ValueError('Invalid party state')
    if (not re.fullmatch(r'[A-Z2-9]{8}', state['code']) or
            type(state['epoch']) is not int or state['epoch'] < 1 or
            type(state['revision']) is not int or state['revision'] < 0 or
            len(state['members']) > 3): raise ValueError('Invalid party state')
    pool = layouts_for(state['difficulty'])
    if state['layout'] is not None and (type(state['layout']) is not int or state['layout'] not in pool):
        raise ValueError('Invalid party layout')
    if type(state['confidence']) not in (int, float) or not math.isfinite(state['confidence']) or not 0 <= state['confidence'] <= 1:
        raise ValueError('Invalid party confidence')
    for member in state['members']:
        username(member['username'])
        if not re.fullmatch(r'[0-9a-f]{16}', member['id']) or member['color'] not in COLORS:
            raise ValueError('Invalid party member')
        point, age = member['position'], member['age']
        if point is not None:
            if (not isinstance(point, list) or len(point) != 2 or
                    any(type(n) not in (int, float) or not math.isfinite(n) or not 0 <= n <= 100 for n in point) or
                    type(age) not in (int, float) or not math.isfinite(age) or age < 0):
                raise ValueError('Invalid party position')
    return state


def updated_state(state, message):
    if message['type']=='state': return read_state(message['state'])
    if message['type']!='positions': raise ValueError('Invalid party message')
    if not state or message['epoch']!=state['epoch'] or message['revision']!=state['revision']:return state
    if not isinstance(message['positions'],list) or len(message['positions'])>3:raise ValueError('Invalid party positions')
    positions={identity:(point,age) for identity,point,age in message['positions']}
    result=dict(state,members=[dict(p,position=positions[p['id']][0],age=positions[p['id']][1]) if p['id'] in positions else dict(p) for p in state['members']])
    return read_state(result)


class PartyClient:
    def __init__(self):
        self.events = queue.Queue(maxsize=8)
        self.commands = queue.Queue(maxsize=4)
        self.stop = threading.Event()
        self.lock = threading.Lock()
        self.latest = None
        self.thread = None

    def start(self, address, name, difficulty='Chaos', code=''):
        address, name = server_url(address), username(name)
        if self.thread and self.thread.is_alive(): raise ValueError('Leave the current party first.')
        self.stop.clear()
        while not self.events.empty(): self.events.get_nowait()
        while not self.commands.empty(): self.commands.get_nowait()
        self.latest = None
        hello = dict(type='join', code=code.strip().upper(), username=name) if code.strip() else dict(type='create', username=name, difficulty=difficulty)
        self.thread = threading.Thread(target=self.worker, args=(address, hello), daemon=True)
        self.thread.start()

    def event(self, value):
        try:self.events.put_nowait(value)
        except queue.Full:
            try:self.events.get_nowait()
            except queue.Empty:pass
            try:self.events.put_nowait(value)
            except queue.Full:pass

    def publish(self, message):
        with self.lock: self.latest = message

    def new_run(self, epoch, difficulty):
        try: self.commands.put_nowait(dict(type='new_run', epoch=epoch, difficulty=difficulty))
        except queue.Full: pass

    def close(self):
        self.stop.set()

    def worker(self, address, hello):
        delay = 1
        while not self.stop.is_set():
            try:
                with connect(address, open_timeout=8, close_timeout=1, compression=None,
                             max_size=8192, max_queue=2, ping_interval=20, ping_timeout=20,
                             proxy=None) as socket:
                    socket.send(json.dumps(dict(hello, version=VERSION)))
                    reply = json.loads(socket.recv(timeout=8))
                    if reply.get('type') == 'error':
                        self.event(dict(type='error', code=reply.get('code', 'connection_failed'))); return
                    if reply.get('type') != 'welcome' or reply.get('version') != VERSION:
                        raise ValueError('Incompatible party server')
                    reply['state'] = read_state(reply['state'])
                    current_state=reply['state']
                    hello = dict(type='resume', id=reply['id'], token=reply['token'], code=reply['state']['code'])
                    # Do not surface the resume secret to widgets or persistence.
                    self.event(dict(type='welcome', id=reply['id'], state=reply['state']))
                    delay = 1
                    sent_at = 0.
                    while not self.stop.is_set():
                        while not self.commands.empty(): socket.send(json.dumps(self.commands.get_nowait()))
                        now = time.monotonic()
                        if now-sent_at >= .5:
                            with self.lock: message, self.latest = self.latest, None
                            if message is not None: socket.send(json.dumps(message, separators=(',', ':')))
                            sent_at = now
                        try: reply = json.loads(socket.recv(timeout=.1))
                        except TimeoutError: continue
                        if reply.get('type') in ('state','positions'):
                            current_state=updated_state(current_state,reply)
                            self.event(dict(type='state', state=current_state))
                        elif reply.get('type') == 'error':
                            self.event(dict(type='error', code=reply.get('code', 'connection_failed'))); return
                    socket.send('{"type":"leave"}')
            except Exception:
                if not self.stop.is_set(): self.event(dict(type='reconnecting'))
            if self.stop.wait(delay*random.uniform(.7,1.3)): return
            delay = min(15, delay*2)
