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


class _StalePartyState(TimeoutError):
    """The relay's advertised periodic full states stopped arriving."""


def _identity(value, optional=False):
    if optional and value is None:
        return None
    if not isinstance(value, str) or not re.fullmatch(r'[0-9a-f]{16}', value):
        raise ValueError('Invalid party identity')
    return value


def _counter(value, minimum=0):
    if type(value) is not int or not minimum <= value <= 2**53-1:
        raise ValueError('Invalid party counter')
    return value


def _number(value, minimum, maximum=float('inf')):
    try:
        valid = type(value) in (int, float) and math.isfinite(value) and minimum <= value <= maximum
    except OverflowError:
        valid = False
    if not valid:
        raise ValueError('Invalid party number')
    return value


def _position(point, age):
    if point is None:
        if age is not None:
            raise ValueError('Invalid party age')
        return None, None
    if not isinstance(point, list) or len(point) != 2:
        raise ValueError('Invalid party position')
    return [_number(n, 0, 100) for n in point], _number(age, 0)


def read_state(state):
    """Project untrusted JSON onto the bounded fields the UI can consume."""
    try:
        if not isinstance(state, dict):
            raise ValueError('Invalid party state')
        code = state['code']
        if not isinstance(code, str) or not re.fullmatch(r'[A-Z2-9]{8}', code):
            raise ValueError('Invalid party code')
        difficulty = state['difficulty']
        if not isinstance(difficulty, str):
            raise ValueError('Invalid party difficulty')
        pool = layouts_for(difficulty)
        epoch, revision = _counter(state['epoch'], 1), _counter(state['revision'])
        layout = state['layout']
        if layout is not None and (type(layout) is not int or layout not in pool):
            raise ValueError('Invalid party layout')
        confidence = _number(state['confidence'], 0, 1)
        host = _identity(state['host'])
        source = _identity(state['source'], optional=True)
        started_by = _identity(state.get('started_by'), optional=True)
        if ((layout is None and (confidence != 0 or source is not None)) or
                (layout is not None and (confidence < .75 or source is None or revision < 1))):
            raise ValueError('Invalid party evidence')
        raw_members = state['members']
        if not isinstance(raw_members, list) or not 1 <= len(raw_members) <= 3:
            raise ValueError('Invalid party members')
        members, identities, colors = [], set(), set()
        for member in raw_members:
            if not isinstance(member, dict):
                raise ValueError('Invalid party member')
            identity = _identity(member['id'])
            color = member['color']
            if identity in identities or not isinstance(color, str) or color not in COLORS or color in colors:
                raise ValueError('Invalid party member')
            if type(member['online']) is not bool:
                raise ValueError('Invalid party presence')
            position, age = _position(member['position'], member['age'])
            if position is not None and layout is None:
                raise ValueError('Invalid party position')
            members.append(dict(id=identity, username=username(member['username']), color=color,
                                online=member['online'], position=position, age=age))
            identities.add(identity)
            colors.add(color)
        if host not in identities:
            raise ValueError('Invalid party host')
        # Evidence source and starter may have left after the reconnect grace
        # period; they remain historical identities in the current relay.
        return dict(code=code, difficulty=difficulty, epoch=epoch, revision=revision,
                    layout=layout, confidence=confidence, host=host, source=source,
                    started_by=started_by, members=members)
    except (KeyError, TypeError) as exc:
        raise ValueError('Invalid party state') from exc


def updated_state(state, message):
    try:
        if not isinstance(message, dict):
            raise ValueError('Invalid party message')
        if message['type'] == 'state':
            return read_state(message['state'])
        if message['type'] != 'positions':
            raise ValueError('Invalid party message')
        epoch, revision = _counter(message['epoch'], 1), _counter(message['revision'])
        if not state or epoch != state['epoch'] or revision != state['revision']:
            return state
        raw = message['positions']
        if not isinstance(raw, list) or len(raw) > 3:
            raise ValueError('Invalid party positions')
        identities = {member['id'] for member in state['members']}
        positions = {}
        for entry in raw:
            if not isinstance(entry, list) or len(entry) != 3:
                raise ValueError('Invalid party positions')
            identity = _identity(entry[0])
            if identity not in identities or identity in positions:
                raise ValueError('Invalid party positions')
            positions[identity] = _position(entry[1], entry[2])
        result = dict(state, members=[dict(member, position=positions[member['id']][0], age=positions[member['id']][1])
                      if member['id'] in positions else dict(member) for member in state['members']])
        return read_state(result)
    except (KeyError, TypeError) as exc:
        raise ValueError('Invalid party message') from exc


def _error_code(reply):
    code = reply.get('code', 'connection_failed')
    if not isinstance(code, str) or not re.fullmatch(r'[a-z_]{1,48}', code):
        raise ValueError('Invalid party error')
    return code


def _welcome(reply):
    if (not isinstance(reply, dict) or reply.get('type') != 'welcome' or
            type(reply.get('version')) is not int or reply['version'] != VERSION):
        raise ValueError('Incompatible party server')
    snapshot = read_state(reply['state'])
    identity = _identity(reply['id'])
    token = reply['token']
    if (identity not in {member['id'] for member in snapshot['members']} or
            not isinstance(token, str) or not re.fullmatch(r'[A-Za-z0-9_-]{16,128}', token)):
        raise ValueError('Invalid party welcome')
    return identity, token, snapshot


class PartyClient:
    def __init__(self):
        self.state_timeout = 45.
        self.events = queue.Queue(maxsize=8)
        self.commands = queue.Queue(maxsize=4)
        self.stop = threading.Event()
        self.lock = threading.Lock()
        self.latest = None
        self.thread = None
        self.resume_session=None;self.preserve_on_close=False

    def start(self, address, name, difficulty='Chaos', code='',resume=None):
        address, name = server_url(address), username(name)
        if self.thread and self.thread.is_alive(): raise ValueError('Leave the current party first.')
        self.stop.clear()
        while not self.events.empty(): self.events.get_nowait()
        while not self.commands.empty(): self.commands.get_nowait()
        self.latest = None
        self.resume_session=None;self.preserve_on_close=False
        hello = dict(type='join', code=code.strip().upper(), username=name) if code.strip() else dict(type='create', username=name, difficulty=difficulty)
        if resume:
            identity=_identity(resume['id']);token=resume['token'];room=resume['code']
            if not isinstance(token,str) or not re.fullmatch(r'[A-Za-z0-9_-]{16,128}',token) or not isinstance(room,str) or not re.fullmatch(r'[A-Z2-9]{8}',room):raise ValueError('Invalid party handoff')
            hello=dict(type='resume',id=identity,token=token,code=room)
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

    def prepare_update(self,path):
        from party_handoff import save
        with self.lock:
            if not self.resume_session:return False
            save(path,self.resume_session)
            self.preserve_on_close=True
        return True

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
                        self.event(dict(type='error', code=_error_code(reply))); return
                    identity, token, current_state = _welcome(reply)
                    interval = reply.get('state_interval')
                    state_timeout = max(self.state_timeout,3*_number(interval,.1,60)) if interval is not None else None
                    last_state_at = time.monotonic()
                    hello = dict(type='resume', id=identity, token=token, code=current_state['code'])
                    # Never put the secret in UI events. Only an explicit update
                    # may persist a single-use, DPAPI-encrypted handoff.
                    with self.lock:self.resume_session=dict(address=address,**hello)
                    self.event(dict(type='welcome', id=identity, state=current_state))
                    delay = 1
                    sent_at = 0.
                    received_at, receive_credit = time.monotonic(), 32.
                    while not self.stop.is_set():
                        while not self.commands.empty(): socket.send(json.dumps(self.commands.get_nowait()))
                        now = time.monotonic()
                        if state_timeout is not None and now-last_state_at >= state_timeout:
                            raise _StalePartyState()
                        if now-sent_at >= .5:
                            with self.lock: message, self.latest = self.latest, None
                            if message is not None: socket.send(json.dumps(message, separators=(',', ':')))
                            sent_at = now
                        try: raw = socket.recv(timeout=.1)
                        except TimeoutError: continue
                        now = time.monotonic()
                        # The genuine relay publishes at most four snapshots/s.
                        # Reject a custom server flood before it can monopolize
                        # parsing or continuously refill the small UI queue.
                        receive_credit = min(32., receive_credit+(now-received_at)*8.)-1
                        received_at = now
                        if receive_credit < 0:
                            raise ValueError('Too many party messages')
                        reply = json.loads(raw)
                        if reply.get('type') in ('state','positions'):
                            current_state=updated_state(current_state,reply)
                            if reply['type']=='state':last_state_at=now
                            # The bounded UI queue may discard the original
                            # welcome while Tk is busy. Every snapshot must be
                            # sufficient to recover this connection's identity.
                            self.event(dict(type='state', id=identity, state=current_state))
                        elif reply.get('type') == 'error':
                            self.event(dict(type='error', code=_error_code(reply))); return
                    if not self.preserve_on_close:socket.send('{"type":"leave"}')
            except Exception as exc:
                if not self.stop.is_set():
                    event=dict(type='reconnecting')
                    if isinstance(exc,_StalePartyState):event['reason']='stale_state'
                    self.event(event)
            if self.stop.wait(delay*random.uniform(.7,1.3)): return
            delay = min(15, delay*2)
