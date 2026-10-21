"""Ephemeral three-person navigation relay. Run with python party_server.py."""
import argparse
import asyncio
from collections import Counter
from http import HTTPStatus
import json
import ipaddress
import logging
import math
import os
import secrets
import time
from websockets.asyncio.server import serve
from websockets.exceptions import ConnectionClosed
from map_catalog import DIFFICULTIES, layouts_for
from party_protocol import COLORS, VERSION, username

# Published ranges: https://www.cloudflare.com/ips-v4/ and /ips-v6/ (2026-10-21).
CF_NETWORKS=tuple(ipaddress.ip_network(cidr) for cidr in (
    '173.245.48.0/20','103.21.244.0/22','103.22.200.0/22','103.31.4.0/22',
    '141.101.64.0/18','108.162.192.0/18','190.93.240.0/20','188.114.96.0/20',
    '197.234.240.0/22','198.41.128.0/17','162.158.0.0/15','104.16.0.0/13',
    '104.24.0.0/14','172.64.0.0/13','131.0.72.0/22','2400:cb00::/32',
    '2606:4700::/32','2803:f800::/32','2405:b500::/32','2405:8100::/32',
    '2a06:98c0::/29','2c0f:f248::/32'))


class Relay:
    def __init__(self, max_rooms=1000, max_connections=3200, per_ip=30, trust_proxy=False):
        self.rooms = {}
        self.connections = Counter()
        self.max_rooms, self.max_connections, self.per_ip = max_rooms, max_connections, per_ip
        self.trust_proxy=trust_proxy

    def state(self, room):
        return dict(code=room['code'], difficulty=room['difficulty'], epoch=room['epoch'],
                    revision=room['revision'], layout=room['layout'], confidence=room['confidence'],
                    source=room['source'], host=room['host'],
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
            message = json.loads(await asyncio.wait_for(socket.recv(), 10))
            if not isinstance(message, dict): raise ValueError('invalid_message')
            kind = message.get('type')
            if kind == 'create':
                name = username(message.get('username'))
                difficulty = message.get('difficulty', 'Chaos')
                if difficulty not in DIFFICULTIES: raise ValueError('invalid_difficulty')
                if len(self.rooms) >= self.max_rooms: raise ValueError('server_full')
                alphabet = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
                code = ''.join(secrets.choice(alphabet) for _ in range(8))
                while code in self.rooms: code = ''.join(secrets.choice(alphabet) for _ in range(8))
                room = dict(code=code, difficulty=difficulty, members={}, epoch=1, revision=0,
                            layout=None, confidence=0., source=None, host=None, dirty=False, positions_dirty=False)
                self.rooms[code] = room
            elif kind in ('join', 'resume'):
                room = self.rooms.get(str(message.get('code', '')).strip().upper())
                if room is None: raise ValueError('party_not_found')
                if kind == 'resume':
                    member = room['members'].get(message.get('id'))
                    if member is None or not secrets.compare_digest(member['token'], str(message.get('token', ''))):
                        member = None; raise ValueError('session_expired')
                    if member['socket'] is not None: raise ValueError('already_connected')
                    name = member['username']
                else:
                    name = username(message.get('username'))
                    if len(room['members']) >= 3: raise ValueError('party_full')
            else: raise ValueError('invalid_message')
            if member is None:
                color = next(c for c in COLORS if c not in [p['color'] for p in room['members'].values()])
                member = dict(id=secrets.token_hex(8), token=secrets.token_urlsafe(32), username=name,
                              color=color, socket=None, position=None, seen=0., disconnected=0.,
                              credit=8., rate_time=time.monotonic(), queue=None)
                room['members'][member['id']] = member
                if room['host'] is None: room['host'] = member['id']
            member['socket'] = socket
            member['queue'] = asyncio.Queue(maxsize=1)
            await socket.send(json.dumps(dict(type='welcome', version=VERSION, id=member['id'],
                                              token=member['token'], state=self.state(room))))
            writer = asyncio.create_task(self.write(socket, member['queue']))
            room['dirty'] = True
            async for raw in socket:
                message = json.loads(raw)
                if not isinstance(message, dict): raise ValueError('invalid_message')
                now = time.monotonic()
                member['credit'] = min(8., member['credit']+(now-member['rate_time'])*3.)-1
                member['rate_time'] = now
                if member['credit'] < 0:
                    await socket.close(1008, 'Too many updates'); break
                if message.get('type') == 'leave': break
                await self.command(room, member, message)
        except (ValueError, TypeError, KeyError) as exc:
            # Return stable codes only; never echo arbitrary client input.
            codes = {'party_full', 'party_not_found', 'server_full', 'session_expired',
                     'invalid_difficulty', 'already_connected', 'invalid_message'}
            code = str(exc) if str(exc) in codes else 'invalid_message'
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
                self.clean_room(room)
            self.connections[address] -= 1
            if not self.connections[address]: del self.connections[address]

    def clean_room(self, room):
        now = time.monotonic()
        for identity, member in list(room['members'].items()):
            if member['socket'] is None and now-member['disconnected'] > 60:
                del room['members'][identity]; room['dirty'] = True
        if not room['members']:
            self.rooms.pop(room['code'], None)
        elif room['host'] not in room['members']:
            room['host'] = next(iter(room['members'])); room['dirty'] = True

    async def command(self, room, member, message):
        if message.get('type') == 'new_run':
            if room['host'] != member['id']: return
            difficulty = message.get('difficulty', room['difficulty'])
            if difficulty not in DIFFICULTIES: raise ValueError('invalid_difficulty')
            if message.get('epoch') != room['epoch']: return
            room.update(epoch=room['epoch']+1, revision=0, layout=None, confidence=0., source=None,
                        difficulty=difficulty, dirty=True)
            for player in room['members'].values(): player['position'] = None
            return
        if message.get('type') != 'update': raise ValueError('invalid_message')
        if message.get('epoch') != room['epoch']: return
        if 'username' in message:
            name=username(message['username'])
            if name!=member['username']:member['username']=name;room['dirty']=True
        evidence = message.get('evidence')
        if evidence is not None:
            if not isinstance(evidence, dict): raise ValueError('invalid_message')
            layout, score = evidence.get('layout'), evidence.get('confidence')
            if (type(layout) is not int or layout not in layouts_for(room['difficulty']) or
                    type(score) not in (int, float) or not math.isfinite(score) or not .75 <= score <= 1):
                raise ValueError('invalid_message')
            if score > room['confidence']:
                if layout != room['layout']:
                    room['revision'] += 1
                    for player in room['members'].values(): player['position'] = None
                room.update(layout=layout, confidence=score, source=member['id'], dirty=True)
        if 'position' in message:
            position = message['position']
            if position is not None and (not isinstance(position, list) or len(position) != 2 or
                    any(type(n) not in (int, float) or not math.isfinite(n) or not 0 <= n <= 100 for n in position)):
                raise ValueError('invalid_message')
            if (room['layout'] is not None and message.get('revision') == room['revision'] and
                    message.get('layout') == room['layout']):
                member.update(position=position, seen=time.monotonic()); room['positions_dirty'] = True

    async def write(self, socket, queue):
        try:
            while True:
                _, payload = await queue.get()
                async with asyncio.timeout(2): await socket.send(payload)
        except (ConnectionClosed, TimeoutError): await socket.close(1013, 'Slow connection')

    async def pump(self):
        while True:
            await asyncio.sleep(.25)
            for room in list(self.rooms.values()):
                self.clean_room(room)
                if not room['dirty'] and not room['positions_dirty']: continue
                full = room['dirty']
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
                    if pending_full and not full:
                        if full_payload is None: full_payload=json.dumps(dict(type='state',state=snapshot),separators=(',', ':'))
                        queue.put_nowait((True,full_payload))
                    else:queue.put_nowait((full,payload))


def health(connection, request):
    if request.path in ('/', '/health'):
        return connection.respond(HTTPStatus.OK, 'Eggheist party relay OK\n')
    if request.path != '/party': return connection.respond(HTTPStatus.NOT_FOUND, 'Not found\n')


async def main(host, port, max_rooms, max_connections, per_ip):
    relay = Relay(max_rooms=max_rooms, max_connections=max_connections, per_ip=per_ip,
                  trust_proxy=os.environ.get('PARTY_TRUST_PROXY')=='1')
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
    asyncio.run(main(args.host, args.port, args.max_rooms, args.max_connections, args.per_ip))
