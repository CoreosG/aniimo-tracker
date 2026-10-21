"""A hostile party member is exercised against a genuine loopback relay."""
import asyncio
import json
import unittest

from websockets.asyncio.client import connect
from websockets.asyncio.server import serve
from websockets.exceptions import ConnectionClosed

from party_server import Relay


class RelayTrustTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.relay=Relay()
        self.server=await serve(self.relay.handle,'127.0.0.1',0,max_size=2048,max_queue=2,compression=None,close_timeout=2)
        self.url=f'ws://127.0.0.1:{self.server.sockets[0].getsockname()[1]}/party'
        self.clients=[]
        self.pump=asyncio.create_task(self.relay.pump())

    async def asyncTearDown(self):
        for client in self.clients:await client.close()
        self.server.close();await self.server.wait_closed()
        self.pump.cancel();await asyncio.gather(self.pump,return_exceptions=True)

    async def request(self,message):
        socket=await connect(self.url)
        self.clients.append(socket)
        await socket.send(json.dumps(message))
        reply=json.loads(await asyncio.wait_for(socket.recv(),2))
        return socket,reply

    async def state_where(self,socket,predicate):
        async with asyncio.timeout(3):
            while True:
                message=json.loads(await socket.recv())
                if message['type']=='state' and predicate(message['state']):return message['state']

    async def error(self,socket):
        async with asyncio.timeout(3):
            while True:
                message=json.loads(await socket.recv())
                if message['type']=='error':return message

    async def test_client_cannot_forward_payloads_forge_other_members_or_cross_party_boundaries(self):
        victim,first=await self.request(dict(type='create',username='Victim'))
        outsider,other=await self.request(dict(type='create',username='Other party'))
        attacker,joined=await self.request(dict(type='join',username='Peer',code=first['state']['code']))
        marker='DO_NOT_FORWARD_RAW_INPUT'
        await attacker.send(json.dumps(dict(type='update',epoch=1,revision=1,layout=32,position=[12,34],
            evidence=dict(layout=32,confidence=.9,command=marker),id=first['id'],host=joined['id'],
            room=other['state']['code'],code=other['state']['code'],members=[dict(id=first['id'],position=[99,99])],
            command=marker,file=marker,url=marker,token=marker)))
        state=await self.state_where(victim,lambda state:state['layout']==32)
        self.assertNotIn(marker,json.dumps(state))
        self.assertEqual(state['host'],first['id'])
        self.assertEqual(next(p['position'] for p in state['members'] if p['id']==first['id']),None)
        self.assertEqual(next(p['position'] for p in state['members'] if p['id']==joined['id']),[12,34])
        await outsider.send(json.dumps(dict(type='update',epoch=1,evidence=dict(layout=39,confidence=.8))))
        separate=await self.state_where(outsider,lambda state:state['layout']==39)
        self.assertEqual(len(separate['members']),1)
        self.assertEqual(separate['code'],other['state']['code'])
        self.assertEqual(separate['confidence'],.8)

    async def test_invalid_position_does_not_partially_apply_identity_or_evidence(self):
        victim,first=await self.request(dict(type='create',username='Victim'))
        attacker,joined=await self.request(dict(type='join',username='Peer',code=first['state']['code']))
        await attacker.send(json.dumps(dict(type='update',epoch=1,username='Injected',
            evidence=dict(layout=39,confidence=1),position=[float('nan'),20])))
        self.assertEqual(await self.error(attacker),dict(type='error',code='invalid_message'))
        state=await self.state_where(victim,lambda state:any(p['id']==joined['id'] and not p['online'] for p in state['members']))
        self.assertIsNone(state['layout'])
        self.assertEqual(next(p['username'] for p in state['members'] if p['id']==joined['id']),'Peer')

    async def test_control_characters_bad_names_and_nonfinite_coordinates_are_rejected_without_echo(self):
        for name in ('','  ','Peer\nlink','\x1b[31m','\u202ehidden',[],None):
            with self.subTest(name=repr(name)):
                _,reply=await self.request(dict(type='create',username=name))
                self.assertEqual(reply,dict(type='error',code='invalid_message'))
        for position in ([float('nan'),20],[float('inf'),20],[True,20],[-1,20],[101,20],{},'file.exe'):
            socket,_=await self.request(dict(type='create',username='Peer'))
            await socket.send(json.dumps(dict(type='update',epoch=1,position=position)))
            self.assertEqual(await self.error(socket),dict(type='error',code='invalid_message'))

    async def test_frame_size_and_update_rate_limits_disconnect_only_the_sender(self):
        victim,first=await self.request(dict(type='create',username='Victim'))
        attacker,_=await self.request(dict(type='join',username='Peer',code=first['state']['code']))
        await attacker.send('x'*2049)
        with self.assertRaises(ConnectionClosed) as closed:
            while True:await attacker.recv()
        self.assertEqual(closed.exception.rcvd.code,1009)
        flood,_=await self.request(dict(type='join',username='Flood',code=first['state']['code']))
        for _ in range(12):await flood.send(json.dumps(dict(type='update',epoch=1)))
        with self.assertRaises(ConnectionClosed) as closed:
            async with asyncio.timeout(4):
                while True:await flood.recv()
        self.assertEqual(closed.exception.rcvd.code,1008)
        await victim.send(json.dumps(dict(type='update',epoch=1,evidence=dict(layout=32,confidence=.9))))
        state=await self.state_where(victim,lambda state:state['layout']==32)
        self.assertEqual(state['host'],first['id'])

    async def test_deep_json_huge_integers_and_bad_counter_types_return_stable_errors(self):
        victim,_=await self.request(dict(type='create',username='Victim'))
        deeply_nested='{"type":"update","epoch":1,"padding":'+'['*1000+'0'+']'*1000+'}'
        payloads=(deeply_nested,
            json.dumps(dict(type='update',epoch=1,evidence=dict(layout=32,confidence=10**1000))),
            json.dumps(dict(type='update',epoch=1,position=[10**1000,20])),
            json.dumps(dict(type='update',epoch=True)),
            json.dumps(dict(type='update',epoch=2**53)),
            json.dumps(dict(type='update',epoch=1,revision=True,username='Injected')))
        for raw in payloads:
            self.assertLessEqual(len(raw.encode()),2048)
            socket,_=await self.request(dict(type='create',username='Peer'))
            await socket.send(raw)
            self.assertEqual(await self.error(socket),dict(type='error',code='invalid_message'))
        await victim.send(json.dumps(dict(type='update',epoch=1,evidence=dict(layout=39,confidence=.9))))
        self.assertEqual((await self.state_where(victim,lambda state:state['layout']==39))['epoch'],1)
