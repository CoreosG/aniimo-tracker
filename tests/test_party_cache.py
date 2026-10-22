"""Restart recovery through the same WebSocket interface used by desktop clients."""
import asyncio
import json
import queue
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
from websockets.asyncio.client import connect
from websockets.asyncio.server import serve
from party_server import Relay
from party_client import PartyClient


class PartyRestartTests(unittest.IsolatedAsyncioTestCase):
    async def test_desktop_reconnects_automatically_to_restarted_relay_with_same_party(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'party-cache.json'
            relay=Relay(cache_path=path)
            server=await serve(relay.handle,'127.0.0.1',0)
            port=server.sockets[0].getsockname()[1]
            pump=asyncio.create_task(relay.pump())
            desktop=PartyClient()
            async def welcome():
                async with asyncio.timeout(6):
                    while True:
                        try:event=desktop.events.get_nowait()
                        except queue.Empty:await asyncio.sleep(.05);continue
                        self.assertNotEqual(event['type'],'error',event)
                        if event['type']=='welcome':return event
            try:
                desktop.start(f'ws://127.0.0.1:{port}','Host')
                first=await welcome()
                async with asyncio.timeout(3):
                    while not path.exists():await asyncio.sleep(.05)
                pump.cancel();await asyncio.gather(pump,return_exceptions=True)
                server.close();await server.wait_closed()
                relay=Relay(cache_path=path)
                server=await serve(relay.handle,'127.0.0.1',port)
                pump=asyncio.create_task(relay.pump())
                restored=await welcome()
                self.assertEqual(restored['id'],first['id'])
                self.assertEqual(restored['state']['code'],first['state']['code'])
                self.assertEqual(restored['state']['host'],first['id'])
            finally:
                desktop.close()
                await asyncio.to_thread(desktop.thread.join,3)
                server.close();await server.wait_closed()
                pump.cancel();await asyncio.gather(pump,return_exceptions=True)

    async def test_explicit_leave_cannot_be_resurrected_by_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'party-cache.json'
            relay=Relay(cache_path=path)
            async with serve(relay.handle,'127.0.0.1',0) as server:
                pump=asyncio.create_task(relay.pump())
                try:
                    url=f'ws://127.0.0.1:{server.sockets[0].getsockname()[1]}'
                    async with connect(url) as client:
                        await client.send(json.dumps(dict(type='create',username='Host')))
                        first=json.loads(await client.recv())
                        async with asyncio.timeout(3):
                            while not path.exists():await asyncio.sleep(.05)
                        previous=path.read_bytes()
                        await client.send('{"type":"leave"}')
                        async with asyncio.timeout(3):
                            while path.read_bytes()==previous:await asyncio.sleep(.05)
                finally:
                    pump.cancel();await asyncio.gather(pump,return_exceptions=True)
            replacement=Relay(cache_path=path)
            async with serve(replacement.handle,'127.0.0.1',0) as server:
                async with connect(f'ws://127.0.0.1:{server.sockets[0].getsockname()[1]}') as client:
                    await client.send(json.dumps(dict(type='resume',code=first['state']['code'],id=first['id'],token=first['token'])))
                    self.assertEqual(json.loads(await client.recv()),dict(type='error',code='party_not_found'))

    async def test_restart_preserves_code_identity_layout_but_not_positions_or_raw_tokens(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'party-cache.json'
            relay = Relay(cache_path=path)
            async with serve(relay.handle, '127.0.0.1', 0) as server:
                url = f'ws://127.0.0.1:{server.sockets[0].getsockname()[1]}'
                pump = asyncio.create_task(relay.pump())
                try:
                    async with connect(url) as host, connect(url) as peer:
                        await host.send(json.dumps(dict(type='create', username='Host')))
                        first = json.loads(await host.recv())
                        await peer.send(json.dumps(dict(type='join', username='Peer', code=first['state']['code'])))
                        joined = json.loads(await peer.recv())
                        await host.send(json.dumps(dict(type='update', epoch=1, revision=1, layout=32,
                            evidence=dict(layout=32, confidence=.9), position=[12,34])))
                        async with asyncio.timeout(3):
                            while True:
                                state = json.loads(await peer.recv()).get('state')
                                if state and state['layout']==32:break
                        async with asyncio.timeout(3):
                            while not path.exists():await asyncio.sleep(.05)
                        # Freeze the last successful checkpoint, simulating process loss.
                        pump.cancel();await asyncio.gather(pump, return_exceptions=True)
                finally:
                    pump.cancel();await asyncio.gather(pump, return_exceptions=True)
            blob = path.read_text()
            self.assertNotIn(first['token'], blob)
            self.assertNotIn(joined['token'], blob)
            self.assertNotIn('position', blob)
            replacement = Relay(cache_path=path)
            async with serve(replacement.handle, '127.0.0.1', 0) as server:
                url = f'ws://127.0.0.1:{server.sockets[0].getsockname()[1]}'
                async with connect(url) as host:
                    await host.send(json.dumps(dict(type='resume',code=first['state']['code'],id=first['id'],token=first['token'])))
                    resumed = json.loads(await host.recv())
                    self.assertEqual(resumed['type'], 'welcome')
                    self.assertEqual(resumed['id'], first['id'])
                    self.assertEqual(resumed['state']['host'], first['id'])
                    self.assertEqual(resumed['state']['layout'], 32)
                    self.assertEqual(len(resumed['state']['members']), 2)
                    self.assertTrue(all(p['position'] is None for p in resumed['state']['members']))
                async with connect(url) as peer:
                    await peer.send(json.dumps(dict(type='resume',code=first['state']['code'],id=joined['id'],token=joined['token'])))
                    resumed = json.loads(await peer.recv())
                    self.assertEqual(resumed['id'], joined['id'])
                async with connect(url) as attacker:
                    await attacker.send(json.dumps(dict(type='resume',code=first['state']['code'],id=first['id'],token='wrong-token')))
                    self.assertEqual(json.loads(await attacker.recv()),dict(type='error',code='session_expired'))
            with patch('party_cache.time.time', return_value=time.time()+61):
                expired = Relay(cache_path=path)
            async with serve(expired.handle, '127.0.0.1', 0) as server:
                url = f'ws://127.0.0.1:{server.sockets[0].getsockname()[1]}'
                async with connect(url) as host:
                    await host.send(json.dumps(dict(type='resume',code=first['state']['code'],id=first['id'],token=first['token'])))
                    self.assertEqual(json.loads(await host.recv()),dict(type='error',code='party_not_found'))

    async def test_unreadable_checkpoint_does_not_prevent_creating_a_new_party(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'party-cache.json'
            path.write_text('{corrupt')
            with self.assertLogs('party.relay',level='INFO') as logs:
                relay=Relay(cache_path=path)
            self.assertTrue(any('cache_restore_failed' in line for line in logs.output))
            async with serve(relay.handle, '127.0.0.1', 0) as server:
                async with connect(f'ws://127.0.0.1:{server.sockets[0].getsockname()[1]}') as client:
                    await client.send(json.dumps(dict(type='create',username='NewHost')))
                    self.assertEqual(json.loads(await client.recv())['type'],'welcome')
