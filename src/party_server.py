"""Ephemeral three-person navigation relay. Run with python party_server.py."""
import argparse
import asyncio
import hashlib
from collections import Counter
from http import HTTPStatus
import json
import ipaddress
import logging
import math
import os
import re
import secrets
import time
from websockets.asyncio.server import serve
from websockets.exceptions import ConnectionClosed
from map_catalog import DIFFICULTIES, layouts_for
from party_protocol import COLORS, VERSION, username
from party_cache import PartyCache

LOG = logging.getLogger('party.relay')


def diagnostic(event, **fields):
    # Callers supply only fixed event names, random diagnostic IDs and numbers.
    LOG.info(json.dumps(dict(event=event, **fields), separators=(',', ':')))

# Published ranges: https://www.cloudflare.com/ips-v4/ and /ips-v6/ (2026-10-21).
CF_NETWORKS=tuple(ipaddress.ip_network(cidr) for cidr in (
    '173.245.48.0/20','103.21.244.0/22','103.22.200.0/22','103.31.4.0/22',
    '141.101.64.0/18','108.162.192.0/18','190.93.240.0/20','188.114.96.0/20',
    '197.234.240.0/22','198.41.128.0/17','162.158.0.0/15','104.16.0.0/13',
    '104.24.0.0/14','172.64.0.0/13','131.0.72.0/22','2400:cb00::/32',
    '2606:4700::/32','2803:f800::/32','2405:b500::/32','2405:8100::/32',
    '2a06:98c0::/29','2c0f:f248::/32'))


def counter(value,minimum=0):
    if type(value) is not int or not minimum<=value<=2**53-1:
        raise ValueError('invalid_message')
    return value


def bounded_number(value,minimum,maximum):
    # Bounds before conversion also reject thousand-digit integers without an
    # OverflowError in math.isfinite(). bool is not a coordinate or score.
    if type(value) not in (int,float) or not minimum<=value<=maximum or not math.isfinite(value):
        raise ValueError('invalid_message')
    return value


def decode_message(raw):
    def invalid_constant(_):raise ValueError('invalid_message')
    message=json.loads(raw,parse_constant=invalid_constant)
    if not isinstance(message,dict) or not isinstance(message.get('type'),str):
        raise ValueError('invalid_message')
    pending=[(message,1)]
    while pending:
        value,depth=pending.pop()
        if depth>16:raise ValueError('invalid_message')
        if isinstance(value,dict):pending.extend((item,depth+1) for item in value.values())
        elif isinstance(value,list):pending.extend((item,depth+1) for item in value)
    return message


class Relay:
    def __init__(self, max_rooms=1000, max_connections=3200, per_ip=30, trust_proxy=False, cache_path=None):
        self.rooms = {}
        self.connections = Counter()
        self.max_rooms, self.max_connections, self.per_ip = max_rooms, max_connections, per_ip
        self.trust_proxy=trust_proxy
        self.state_interval = 15.
        self.metrics = Counter()
        self.last_summary = time.monotonic()
        self.cache = PartyCache(cache_path) if cache_path else None
        self.last_cache = 0.
        self.cache_retry = 0.
        self.cache_dirty = self.cache is not None
        if self.cache:
            try:
                for record in self.cache.load(max_rooms):
                    members = {}
                    for saved in record.pop('members'):
                        remaining=saved.pop('remaining')
                        member=dict(saved,socket=None,position=None,seen=0.,queue=None,
                                    disconnected=time.monotonic()-60+remaining,credit=8.,rate_time=time.monotonic())
                        members[member['id']]=member
                    room=dict(record,members=members,diagnostic_id=secrets.token_hex(6),last_full=0.,
                              dirty=True,positions_dirty=False)
                    if room['host'] not in members:room['host']=next(iter(members))
                    self.rooms[room['code']]=room
                diagnostic('cache_restored', rooms=len(self.rooms))
            except (OSError,ValueError,TypeError,KeyError,RecursionError,OverflowError):
                self.rooms.clear()
                diagnostic('cache_restore_failed')

    def room_event(self, event, room, **fields):
        diagnostic(event, room=room['diagnostic_id'], members=len(room['members']),
                   online=sum(p['socket'] is not None for p in room['members'].values()), **fields)

    def state(self, room):
        return dict(code=room['code'], difficulty=room['difficulty'], epoch=room['epoch'],
                    revision=room['revision'], layout=room['layout'], confidence=room['confidence'],
                    source=room['source'], host=room['host'], started_by=room.get('started_by'),
                    members=[dict(id=p['id'], username=p['username'], color=p['color'],
                                  online=p['socket'] is not None, position=p['position'],
                                  age=round(time.monotonic()-p['seen'], 1) if p['position'] else None)
                             for p in room['members'].values()])

    async def handle(self, socket):
        address = socket.remote_address[0] if socket.remote_address else 'unknown'
        # Behind our loopback proxy, use its overwritten peer header only.
        if address in ('127.0.0.1', '::1') or self.trust_proxy:
            address = socket.request.headers.get('X-Real-IP', address)
            try:
                edge=ipaddress.ip_address(address)
                if any(edge in network for network in CF_NETWORKS):
                    address=str(ipaddress.ip_address(socket.request.headers.get('CF-Connecting-IP',address)))
            except ValueError:
                await socket.close(1008,'Invalid proxy address');return
        if sum(self.connections.values()) >= self.max_connections or self.connections[address] >= self.per_ip:
            await socket.close(1013, 'Server busy'); return
        self.connections[address] += 1
        room = member = writer = None
        try:
            message = decode_message(await asyncio.wait_for(socket.recv(), 10))
            if 'version' in message and (type(message['version']) is not int or message['version']!=VERSION):
                raise ValueError('invalid_message')
            kind = message.get('type')
            if kind == 'create':
                name = username(message.get('username'))
                difficulty = message.get('difficulty', 'Chaos')
                if not isinstance(difficulty,str) or difficulty not in DIFFICULTIES: raise ValueError('invalid_difficulty')
                if len(self.rooms) >= self.max_rooms: raise ValueError('server_full')
                alphabet = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
                code = ''.join(secrets.choice(alphabet) for _ in range(8))
                while code in self.rooms: code = ''.join(secrets.choice(alphabet) for _ in range(8))
                room = dict(code=code, difficulty=difficulty, members={}, epoch=1, revision=0,
                            layout=None, confidence=0., source=None, host=None, dirty=False, positions_dirty=False,
                            diagnostic_id=secrets.token_hex(6), last_full=0.)
                self.rooms[code] = room
            elif kind in ('join', 'resume'):
                code=message.get('code')
                if not isinstance(code,str):raise ValueError('invalid_message')
                room = self.rooms.get(code.strip().upper())
                if room is None: raise ValueError('party_not_found')
                if kind == 'resume':
                    identity,token=message.get('id'),message.get('token')
                    if (not isinstance(identity,str) or not re.fullmatch(r'[0-9a-f]{16}',identity) or
                            not isinstance(token,str) or len(token)>128):raise ValueError('invalid_message')
                    member = room['members'].get(identity)
                    if member is None or not secrets.compare_digest(member['token_hash'], hashlib.sha256(token.encode()).hexdigest()):
                        member = None; raise ValueError('session_expired')
                    if member['socket'] is not None: raise ValueError('already_connected')
                    name = member['username']
                else:
                    name = username(message.get('username'))
                    if len(room['members']) >= 3: raise ValueError('party_full')
            else: raise ValueError('invalid_message')
            if member is None:
                color = next(c for c in COLORS if c not in [p['color'] for p in room['members'].values()])
                token=secrets.token_urlsafe(32)
                member = dict(id=secrets.token_hex(8), token_hash=hashlib.sha256(token.encode()).hexdigest(), username=name,
                              color=color, socket=None, position=None, seen=0., disconnected=0.,
                              credit=8., rate_time=time.monotonic(), queue=None)
                room['members'][member['id']] = member
                if room['host'] is None: room['host'] = member['id']
            member['socket'] = socket
            member['queue'] = asyncio.Queue(maxsize=1)
            link = secrets.token_hex(6)
            await socket.send(json.dumps(dict(type='welcome', version=VERSION, id=member['id'],
                                              token=token, state=self.state(room))))
            self.room_event('member_connected', room, link=link, resumed=kind=='resume')
            writer = asyncio.create_task(self.write(socket, member['queue'], room, link))
            room['dirty'] = True
            async for raw in socket:
                message = decode_message(raw)
                now = time.monotonic()
                member['credit'] = min(8., member['credit']+(now-member['rate_time'])*3.)-1
                member['rate_time'] = now
                if member['credit'] < 0:
                    await socket.close(1008, 'Too many updates'); break
                if message.get('type') == 'leave': break
                await self.command(room, member, message)
        except (ValueError, TypeError, KeyError, RecursionError, OverflowError) as exc:
            # Return stable codes only; never echo arbitrary client input.
            codes = {'party_full', 'party_not_found', 'server_full', 'session_expired',
                     'invalid_difficulty', 'already_connected', 'invalid_message'}
            code = str(exc) if str(exc) in codes else 'invalid_message'
            self.metrics['rejected_messages'] += 1
            try: await socket.send(json.dumps(dict(type='error', code=code)))
            except ConnectionClosed: pass
        except (ConnectionClosed, TimeoutError): pass
        finally:
            if writer is not None:
                writer.cancel(); await asyncio.gather(writer, return_exceptions=True)
            if member is not None and member['socket'] is socket:
                member['socket'] = None; member['disconnected'] = time.monotonic()
                room['dirty'] = True
                if 'message' in locals() and isinstance(message, dict) and message.get('type') == 'leave':
                    room['members'].pop(member['id'], None)
                self.room_event('member_disconnected', room, link=link)
                self.clean_room(room)
            self.connections[address] -= 1
            if not self.connections[address]: del self.connections[address]

    def clean_room(self, room):
        now = time.monotonic()
        for identity, member in list(room['members'].items()):
            if member['socket'] is None and now-member['disconnected'] > 60:
                del room['members'][identity]; room['dirty'] = True
                self.room_event('reservation_expired', room)
        if not room['members']:
            self.rooms.pop(room['code'], None)
            self.cache_dirty = True
        elif room['host'] not in room['members']:
            room['host'] = next(iter(room['members'])); room['dirty'] = True

    async def command(self, room, member, message):
        if message.get('type') == 'new_run':
            difficulty = message.get('difficulty', room['difficulty'])
            if not isinstance(difficulty,str) or difficulty not in DIFFICULTIES: raise ValueError('invalid_difficulty')
            epoch=counter(message.get('epoch'),1)
            if room['host'] != member['id'] and difficulty != room['difficulty']: return
            if epoch != room['epoch']: return
            room.update(epoch=room['epoch']+1, revision=0, layout=None, confidence=0., source=None,
                        difficulty=difficulty, started_by=member['id'], dirty=True)
            for player in room['members'].values(): player['position'] = None
            return
        if message.get('type') != 'update': raise ValueError('invalid_message')
        # Validate the entire update before changing any shared state. A bad
        # position must not sneak in a rename or stronger layout first.
        epoch=counter(message.get('epoch'),1)
        # Old-run packets may carry the previous difficulty's layout pool.
        # Ignore them without touching state or disconnecting a genuine peer.
        if epoch!=room['epoch']:return
        name=username(message['username']) if 'username' in message else member['username']
        revision=counter(message['revision']) if 'revision' in message else None
        position_layout=message.get('layout')
        if position_layout is not None and (type(position_layout) is not int or position_layout not in layouts_for(room['difficulty'])):
            raise ValueError('invalid_message')
        evidence = message.get('evidence')
        if evidence is not None:
            if not isinstance(evidence, dict): raise ValueError('invalid_message')
            layout, score = evidence.get('layout'), evidence.get('confidence')
            if type(layout) is not int or layout not in layouts_for(room['difficulty']):
                raise ValueError('invalid_message')
            bounded_number(score,.75,1)
        if 'position' in message:
            position=message['position']
            if position is not None:
                if not isinstance(position,list) or len(position)!=2:raise ValueError('invalid_message')
                for coordinate in position:bounded_number(coordinate,0,100)
        if name!=member['username']:member['username']=name;room['dirty']=True
        if evidence is not None:
            if score > room['confidence']:
                if layout != room['layout']:
                    room['revision'] += 1
                    for player in room['members'].values(): player['position'] = None
                room.update(layout=layout, confidence=score, source=member['id'], dirty=True)
        if 'position' in message:
            if (room['layout'] is not None and revision == room['revision'] and
                    position_layout == room['layout']):
                member.update(position=position, seen=time.monotonic()); room['positions_dirty'] = True

    async def write(self, socket, queue, room, link):
        roster = None
        try:
            while True:
                full, payload = await queue.get()
                async with asyncio.timeout(2): await socket.send(payload)
                self.metrics['full_sent' if full else 'positions_sent'] += 1
                if full:
                    snapshot = json.loads(payload)['state']
                    signature = tuple((p['id'], p['online']) for p in snapshot['members'])
                    if signature != roster:
                        roster = signature
                        diagnostic('roster_sent', room=room['diagnostic_id'], link=link,
                                   members=len(signature), online=sum(online for _, online in signature))
        except (ConnectionClosed, TimeoutError):
            self.metrics['writer_failures'] += 1
            self.room_event('writer_failed', room, link=link)
            await socket.close(1013, 'Slow connection')

    async def pump(self):
        while True:
            await asyncio.sleep(.25)
            now = time.monotonic()
            changed = False
            if now-self.last_summary >= 60:
                diagnostic('health', rooms=len(self.rooms), connections=sum(self.connections.values()), **self.metrics)
                self.metrics.clear()
                self.last_summary = now
            for room in list(self.rooms.values()):
                self.clean_room(room)
                changed = changed or room['dirty']
                full = room['dirty'] or now-room['last_full'] >= self.state_interval
                if not full and not room['positions_dirty']: continue
                if full: room['last_full'] = now
                room['dirty'] = room['positions_dirty'] = False
                snapshot = self.state(room)
                full_payload = json.dumps(dict(type='state', state=snapshot), separators=(',', ':')) if full else None
                payload = full_payload if full else json.dumps(dict(type='positions', epoch=room['epoch'], revision=room['revision'],
                    positions=[[p['id'],p['position'],p['age']] for p in snapshot['members']]),separators=(',', ':'))
                # Each socket has one replaceable pending state and its own writer.
                # One slow party never delays broadcasts for another party.
                for member in room['members'].values():
                    queue = member['queue']
                    if member['socket'] is None or queue is None: continue
                    pending_full = queue.get_nowait()[0] if queue.full() else False
                    if pending_full: self.metrics['full_coalesced'] += 1
                    if pending_full and not full:
                        if full_payload is None: full_payload=json.dumps(dict(type='state',state=snapshot),separators=(',', ':'))
                        queue.put_nowait((True,full_payload))
                    else:queue.put_nowait((full,payload))
            self.cache_dirty = self.cache_dirty or changed
            if self.cache and now>=self.cache_retry and (self.cache_dirty or (self.rooms and now-self.last_cache>=10)):
                snapshot=self.cache.snapshot(self.rooms)
                self.last_cache=now
                self.cache_dirty=False
                try:
                    await asyncio.to_thread(self.cache.save,snapshot)
                    self.cache_retry=now+1
                except (OSError,ValueError):
                    self.cache_dirty=True
                    self.metrics['cache_failures']+=1
                    self.cache_retry=now+10
                    diagnostic('cache_save_failed')


def health(connection, request):
    if request.path in ('/', '/health'):
        return connection.respond(HTTPStatus.OK, 'Eggheist party relay OK\n')
    if request.path != '/party': return connection.respond(HTTPStatus.NOT_FOUND, 'Not found\n')


async def main(host, port, max_rooms, max_connections, per_ip):
    relay = Relay(max_rooms=max_rooms, max_connections=max_connections, per_ip=per_ip,
                  trust_proxy=os.environ.get('PARTY_TRUST_PROXY')=='1',
                  cache_path=os.environ.get('PARTY_CACHE_PATH'))
    async with serve(relay.handle, host, port, process_request=health, compression=None,
                     max_size=2048, max_queue=2, write_limit=8192, ping_interval=20,
                     ping_timeout=20, close_timeout=2, server_header=None):
        await relay.pump()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default=os.environ.get('PARTY_HOST', '127.0.0.1'))
    parser.add_argument('--port', type=int, default=int(os.environ.get('PARTY_PORT', '8787')))
    parser.add_argument('--max-rooms', type=int, default=int(os.environ.get('PARTY_MAX_ROOMS', '1000')))
    parser.add_argument('--max-connections', type=int, default=int(os.environ.get('PARTY_MAX_CONNECTIONS', '3200')))
    parser.add_argument('--per-ip', type=int, default=int(os.environ.get('PARTY_PER_IP', '30')))
    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING)
    LOG.setLevel(logging.INFO)
    asyncio.run(main(args.host, args.port, args.max_rooms, args.max_connections, args.per_ip))
