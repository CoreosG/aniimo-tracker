import asyncio
import json
import unittest
from websockets.asyncio.client import connect
from websockets.asyncio.server import serve
from party_server import Relay
from party_client import updated_state


class PartyTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.relay = Relay()
        self.server = await serve(self.relay.handle, '127.0.0.1', 0)
        self.url = f'ws://127.0.0.1:{self.server.sockets[0].getsockname()[1]}/party'
        self.clients = []
        self.states = {}
        self.pump = asyncio.create_task(self.relay.pump())

    async def asyncTearDown(self):
        for client in self.clients: await client.close()
        self.server.close(); await self.server.wait_closed()
        self.pump.cancel()
        await asyncio.gather(self.pump, return_exceptions=True)

    async def request(self, payload, headers=None):
        client = await connect(self.url,additional_headers=headers)
        self.clients.append(client)
        await client.send(json.dumps(payload))
        reply=json.loads(await asyncio.wait_for(client.recv(), 2))
        if reply['type']=='welcome':self.states[client]=reply['state']
        return client, reply

    async def test_random_party_code_allows_three_named_players_and_rejects_fourth(self):
        _, first = await self.request(dict(type='create', username='Alice', difficulty='Chaos'))
        self.assertEqual(first['type'], 'welcome')
        self.assertRegex(first['state']['code'], r'^[A-Z2-9]{8}$')
        code = first['state']['code']
        for name in ('Beto', 'Céu'):
            _, joined = await self.request(dict(type='join', username=name, code=code))
            self.assertEqual(joined['type'], 'welcome')
        _, fourth = await self.request(dict(type='join', username='Fourth', code=code))
        self.assertEqual(fourth, dict(type='error', code='party_full'))

    async def state_where(self, client, predicate):
        async with asyncio.timeout(3):
            while True:
                message = json.loads(await client.recv())
                if message['type'] in ('state','positions'):
                    self.states[client]=updated_state(self.states[client],message)
                    if predicate(self.states[client]):return self.states[client]

    async def test_stronger_layout_replaces_for_all_and_invalidates_old_positions(self):
        alice, first = await self.request(dict(type='create', username='Alice', difficulty='Chaos'))
        beto, _ = await self.request(dict(type='join', username='Beto', code=first['state']['code']))
        await alice.send(json.dumps(dict(type='update', epoch=1, evidence=dict(layout=32, confidence=.85))))
        found = await self.state_where(beto, lambda s:s['layout'] == 32)
        self.assertEqual((found['confidence'], found['revision']), (.85, 1))
        await alice.send(json.dumps(dict(type='update', epoch=1, revision=1, layout=32, position=[20, 40])))
        await self.state_where(beto, lambda s:any(p['position'] for p in s['members']))
        await beto.send(json.dumps(dict(type='update', epoch=1, evidence=dict(layout=39, confidence=.96))))
        corrected = await self.state_where(alice, lambda s:s['layout'] == 39)
        self.assertEqual(corrected['revision'], 2)
        self.assertTrue(all(p['position'] is None for p in corrected['members']))
        await alice.send(json.dumps(dict(type='update', epoch=1, revision=1, layout=32, position=[99, 99], evidence=dict(layout=32, confidence=.9))))
        await beto.send(json.dumps(dict(type='update', epoch=1, revision=2, layout=39, position=[11, 22])))
        stable = await self.state_where(alice, lambda s:any(p['position'] == [11, 22] for p in s['members']))
        self.assertEqual(stable['layout'], 39)
        self.assertTrue(all(p['position'] != [99, 99] for p in stable['members']))

    async def test_new_shared_run_clears_layout_and_rejects_delayed_previous_run(self):
        host, first = await self.request(dict(type='create', username='Host', difficulty='Chaos'))
        peer, _ = await self.request(dict(type='join', username='Peer', code=first['state']['code']))
        await host.send(json.dumps(dict(type='update', epoch=1, evidence=dict(layout=32, confidence=.88))))
        await self.state_where(peer, lambda s:s['layout'] == 32)
        await host.send(json.dumps(dict(type='new_run', epoch=1, difficulty='Hard')))
        fresh = await self.state_where(peer, lambda s:s['epoch'] == 2)
        self.assertIsNone(fresh['layout'])
        self.assertEqual(fresh['difficulty'], 'Hard')
        await peer.send(json.dumps(dict(type='update', epoch=1, evidence=dict(layout=39, confidence=1.))))
        await host.send(json.dumps(dict(type='update', epoch=2, evidence=dict(layout=41, confidence=.8))))
        state = await self.state_where(peer, lambda s:s['layout'] == 41)
        self.assertEqual((state['confidence'], state['epoch']), (.8, 2))

    async def test_reconnect_restores_identity_without_broadcasting_session_secret(self):
        host, first = await self.request(dict(type='create', username='Álice', difficulty='Chaos'))
        peer, joined = await self.request(dict(type='join', username='Peer', code=first['state']['code']))
        self.assertNotIn(first['token'], json.dumps(joined['state']))
        await host.close()
        await self.state_where(peer, lambda s:any(not p['online'] for p in s['members']))
        _, resumed = await self.request(dict(type='resume', code=first['state']['code'], id=first['id'], token=first['token']))
        self.assertEqual(resumed['id'], first['id'])
        self.assertEqual(len(resumed['state']['members']), 2)

    async def test_invalid_coordinates_cannot_enter_shared_state(self):
        host, first = await self.request(dict(type='create', username='Host', difficulty='Chaos'))
        await host.send(json.dumps(dict(type='update', epoch=1, evidence=dict(layout=32, confidence=.9))))
        state = await self.state_where(host, lambda s:s['layout'] == 32)
        await host.send(json.dumps(dict(type='update', epoch=1, revision=state['revision'], layout=32, position=[float('nan'), 20])))
        reply = json.loads(await asyncio.wait_for(host.recv(), 2))
        self.assertEqual(reply, dict(type='error', code='invalid_message'))

    async def test_cloudflare_visitors_have_separate_limits_and_untrusted_headers_do_not(self):
        self.relay.per_ip=1
        headers={'X-Real-IP':'173.245.48.5','CF-Connecting-IP':'198.51.100.10'}
        _, first=await self.request(dict(type='create',username='A'),headers)
        self.assertEqual(first['type'],'welcome')
        headers['CF-Connecting-IP']='198.51.100.11'
        _, second=await self.request(dict(type='create',username='B'),headers)
        self.assertEqual(second['type'],'welcome')
        # A direct visitor cannot claim a different IP through a Cloudflare header.
        headers={'X-Real-IP':'203.0.113.1','CF-Connecting-IP':'198.51.100.12'}
        await self.request(dict(type='create',username='C'),headers)
        client=await connect(self.url,additional_headers=dict(headers,**{'CF-Connecting-IP':'198.51.100.13'}))
        self.clients.append(client)
        from websockets.exceptions import ConnectionClosed
        with self.assertRaises(ConnectionClosed):await client.recv()

    async def test_disconnected_player_keeps_a_last_known_position_during_reconnect(self):
        host, first=await self.request(dict(type='create',username='Host'))
        peer,_=await self.request(dict(type='join',username='Peer',code=first['state']['code']))
        await host.send(json.dumps(dict(type='update',epoch=1,evidence=dict(layout=32,confidence=.9))))
        await self.state_where(peer,lambda s:s['layout']==32)
        await host.send(json.dumps(dict(type='update',epoch=1,revision=1,layout=32,position=[12,34])))
        await self.state_where(peer,lambda s:any(p['position']==[12,34] for p in s['members']))
        await host.close()
        state=await self.state_where(peer,lambda s:any(not p['online'] for p in s['members']))
        disconnected=next(p for p in state['members'] if not p['online'])
        self.assertEqual(disconnected['position'],[12,34])


if __name__ == '__main__': unittest.main()
