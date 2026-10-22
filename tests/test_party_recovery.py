"""Real desktop/relay traffic through a fault-injecting TCP proxy."""
import asyncio
import json
import queue
import unittest
from websockets.asyncio.server import serve
from websockets.asyncio.client import connect
from party_client import PartyClient, updated_state
from party_server import Relay


class FaultProxy:
    def __init__(self, port):
        self.port=port;self.links=[];self.tasks=set()

    async def start(self):
        self.server=await asyncio.start_server(self.forward,'127.0.0.1',0)
        return f'ws://127.0.0.1:{self.server.sockets[0].getsockname()[1]}/party'

    async def forward(self, reader, writer):
        task=asyncio.current_task();self.tasks.add(task)
        upstream_reader,upstream=await asyncio.open_connection('127.0.0.1',self.port)
        link=dict(down=writer,up=upstream,hold=False,block_up=False)
        self.links.append(link)
        async def copy(source,destination,downstream=False):
            try:
                while data:=await source.read(65536):
                    if downstream and link['hold']:continue
                    if not downstream and link['block_up']:continue
                    destination.write(data);await destination.drain()
            finally:
                if not link['hold']:destination.close()
        workers=[asyncio.create_task(copy(reader,upstream)),asyncio.create_task(copy(upstream_reader,writer,True))]
        try:await asyncio.gather(*workers)
        finally:
            for worker in workers:worker.cancel()
            await asyncio.gather(*workers,return_exceptions=True)
            writer.close();upstream.close();self.tasks.discard(task)

    def drop(self, index=0, keep_server_open=False):
        link=self.links[index]
        link['hold']=keep_server_open
        link['down'].transport.abort()
        if not keep_server_open:link['up'].transport.abort()

    async def close(self):
        self.server.close();await self.server.wait_closed()
        for link in self.links:link['down'].close();link['up'].close()
        tasks=list(self.tasks)
        for task in tasks:task.cancel()
        await asyncio.gather(*tasks,return_exceptions=True)


class SilentDataProxy:
    """Freeze application messages while WebSocket control traffic stays healthy."""
    def __init__(self, port, legacy=False):
        self.port=port;self.links=[];self.legacy=legacy

    async def start(self):
        self.server=await serve(self.forward,'127.0.0.1',0,ping_interval=.1,ping_timeout=.3,close_timeout=.2)
        return f'ws://127.0.0.1:{self.server.sockets[0].getsockname()[1]}/party'

    async def forward(self, socket):
        async with connect(f'ws://127.0.0.1:{self.port}/party',close_timeout=.2) as upstream:
            link=dict(socket=socket,silent=False);self.links.append(link)
            async def copy(source,destination,downstream=False):
                async for raw in source:
                    if downstream and link['silent']:continue
                    if downstream and self.legacy:
                        message=json.loads(raw)
                        if message['type']=='welcome':message.pop('state_interval',None)
                        raw=json.dumps(message)
                    await destination.send(raw)
            workers=[asyncio.create_task(copy(socket,upstream)),asyncio.create_task(copy(upstream,socket,True))]
            try:await asyncio.wait(workers,return_when=asyncio.FIRST_COMPLETED)
            finally:
                for worker in workers:worker.cancel()
                await asyncio.gather(*workers,return_exceptions=True)

    async def close(self):
        self.server.close();await self.server.wait_closed()


class PartyRecoveryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.relay=Relay()
        self.server=await serve(self.relay.handle,'127.0.0.1',0,close_timeout=.25)
        self.pump=asyncio.create_task(self.relay.pump())
        self.proxy=FaultProxy(self.server.sockets[0].getsockname()[1])
        self.url=await self.proxy.start()
        self.client=PartyClient()

    async def asyncTearDown(self):
        self.client.close()
        await self.proxy.close()
        self.server.close();await self.server.wait_closed()
        if self.client.thread:await asyncio.to_thread(self.client.thread.join,3)
        self.pump.cancel();await asyncio.gather(self.pump,return_exceptions=True)

    async def event(self, predicate):
        async with asyncio.timeout(6):
            while True:
                try:event=self.client.events.get_nowait()
                except queue.Empty:await asyncio.sleep(.02);continue
                self.assertNotEqual(event['type'],'error',event)
                if predicate(event):return event

    async def test_reconnect_recovers_same_identity_when_old_server_socket_is_half_open(self):
        self.client.start(self.url,'Player')
        first=await self.event(lambda e:e['type']=='welcome')
        self.proxy.drop(keep_server_open=True)
        await self.event(lambda e:e['type']=='reconnecting')
        resumed=await self.event(lambda e:e['type']=='welcome')
        self.assertEqual(resumed['id'],first['id'])
        self.assertEqual(resumed['state']['code'],first['state']['code'])
        self.assertEqual(len(resumed['state']['members']),1)

    async def test_silent_party_data_stall_recovers_even_while_pings_and_outgoing_positions_work(self):
        self.relay.state_interval=.1
        await self.proxy.close()
        self.proxy=SilentDataProxy(self.server.sockets[0].getsockname()[1])
        url=await self.proxy.start()
        self.client.state_timeout=1.5
        host_url=f'ws://127.0.0.1:{self.server.sockets[0].getsockname()[1]}/party'
        async with connect(host_url) as host:
            await host.send('{"type":"create","username":"Host"}')
            first=json.loads(await host.recv());state=first['state']
            self.client.start(url,'Peer',code=state['code'])
            peer=await self.event(lambda e:e['type']=='welcome')
            await host.send(json.dumps(dict(type='update',epoch=1,evidence=dict(layout=32,confidence=.9))))
            await self.event(lambda e:e.get('state',{}).get('layout')==32)
            self.proxy.links[0]['silent']=True
            self.client.publish(dict(type='update',epoch=1,revision=1,layout=32,position=[21,43]))
            async with asyncio.timeout(1):
                while True:
                    message=json.loads(await host.recv());state=updated_state(state,message)
                    if any(p['id']==peer['id'] and p['position']==[21,43] for p in state['members']):break
                pong=await self.proxy.links[0]['socket'].ping()
                await pong
            # Other players can still see this client's movement, but its own
            # incoming party messages are frozen despite successful Ping/Pong.
            await host.send(json.dumps(dict(type='update',epoch=1,revision=1,layout=32,position=[61,72])))
            reconnecting=await self.event(lambda e:e['type']=='reconnecting')
            self.assertEqual(reconnecting.get('reason'),'stale_state')
            resumed=await self.event(lambda e:e['type']=='welcome')
            self.assertEqual(resumed['id'],peer['id'])
            self.assertTrue(any(p['id']==first['id'] and p['position']==[61,72] for p in resumed['state']['members']))

    async def test_legacy_relay_without_refresh_capability_can_remain_idle(self):
        self.relay.state_interval=.1
        await self.proxy.close()
        self.proxy=SilentDataProxy(self.server.sockets[0].getsockname()[1],legacy=True)
        self.client.state_timeout=.2
        self.client.start(await self.proxy.start(),'Peer')
        await self.event(lambda e:e['type']=='welcome')
        self.proxy.links[0]['silent']=True
        await asyncio.sleep(.8)
        while True:
            try:event=self.client.events.get_nowait()
            except queue.Empty:break
            self.assertNotIn(event['type'],('reconnecting','error'))
        async with asyncio.timeout(1):
            pong=await self.proxy.links[0]['socket'].ping();await pong
        self.assertTrue(self.client.thread.is_alive())

    async def test_healthy_periodic_full_states_keep_an_idle_client_connected(self):
        self.relay.state_interval=.1
        self.client.state_timeout=.3
        self.client.start(self.url,'Peer')
        first=await self.event(lambda e:e['type']=='welcome')
        await asyncio.sleep(1.)
        seen=await self.event(lambda e:e['type']=='state')
        self.assertEqual(seen['state']['code'],first['state']['code'])
        self.assertEqual(len(self.proxy.links),1)

    async def test_repeated_abrupt_and_half_open_drops_restore_two_way_positions(self):
        url=f'ws://127.0.0.1:{self.server.sockets[0].getsockname()[1]}/party'
        async with connect(url) as host:
            await host.send('{"type":"create","username":"Host"}')
            first=json.loads(await host.recv())
            state=first['state']
            self.client.start(self.url,'Peer',code=state['code'])
            peer=await self.event(lambda e:e['type']=='welcome')
            await host.send(json.dumps(dict(type='update',epoch=1,evidence=dict(layout=32,confidence=.9))))
            await self.event(lambda e:e.get('state',{}).get('layout')==32)
            for half_open,point in ((False,[11,22]),(True,[33,44]),(True,[55,66])):
                self.proxy.drop(len(self.proxy.links)-1,keep_server_open=half_open)
                await self.event(lambda e:e['type']=='reconnecting')
                resumed=await self.event(lambda e:e['type']=='welcome')
                self.assertEqual(resumed['id'],peer['id'])
                self.assertEqual(resumed['state']['layout'],32)
                self.assertEqual(len(resumed['state']['members']),2)
                self.client.publish(dict(type='update',epoch=1,revision=1,layout=32,position=point))
                async with asyncio.timeout(4):
                    while True:
                        message=json.loads(await host.recv())
                        state=updated_state(state,message)
                        if any(p['id']==peer['id'] and p['position']==point and p['online'] for p in state['members']):break
                await host.send(json.dumps(dict(type='update',epoch=1,revision=1,layout=32,position=[77,88])))
                seen=await self.event(lambda e:any(p['id']==first['id'] and p['position']==[77,88] for p in e.get('state',{}).get('members',[])))
                self.assertTrue(any(p['id']==peer['id'] and p['online'] for p in seen['state']['members']))

    async def test_one_way_outage_recovers_after_heartbeat_detects_missing_pongs(self):
        # Only this instance uses short heartbeat timings; the half-open race
        # above retains production timings so it cannot pass by timing out first.
        async with serve(self.relay.handle,'127.0.0.1',0,ping_interval=.1,ping_timeout=.15,close_timeout=.15) as server:
            proxy=FaultProxy(server.sockets[0].getsockname()[1])
            try:
                self.client.start(await proxy.start(),'Peer')
                first=await self.event(lambda e:e['type']=='welcome')
                proxy.links[0]['block_up']=True
                await self.event(lambda e:e['type']=='reconnecting')
                resumed=await self.event(lambda e:e['type']=='welcome')
                self.assertEqual(resumed['id'],first['id'])
                self.assertEqual(resumed['state']['code'],first['state']['code'])
            finally:
                self.client.close()
                await proxy.close()

    async def test_replaced_live_client_stops_retrying_instead_of_fighting_new_transport(self):
        url=f'ws://127.0.0.1:{self.server.sockets[0].getsockname()[1]}/party'
        async with connect(url) as original:
            await original.send('{"type":"create","username":"Player"}')
            first=json.loads(await original.recv())
        resume=dict(code=first['state']['code'],id=first['id'],token=first['token'])
        self.client.start(self.url,'Player',resume=resume)
        await self.event(lambda e:e['type']=='welcome')
        async with connect(url) as replacement:
            await replacement.send(json.dumps(dict(type='resume',**resume)))
            welcomed=json.loads(await replacement.recv())
            self.assertEqual(welcomed['id'],first['id'])
            async with asyncio.timeout(3):
                while True:
                    try:event=self.client.events.get_nowait()
                    except queue.Empty:await asyncio.sleep(.02);continue
                    if event['type']=='error':break
            self.assertEqual(event['code'],'session_replaced')
            await asyncio.to_thread(self.client.thread.join,3)
            self.assertFalse(self.client.thread.is_alive())
            await replacement.send(json.dumps(dict(type='update',epoch=1,evidence=dict(layout=32,confidence=.9))))
            async with asyncio.timeout(3):
                while True:
                    message=json.loads(await replacement.recv())
                    if message.get('state',{}).get('layout')==32:break
            self.assertEqual(len(message['state']['members']),1)
            self.assertTrue(message['state']['members'][0]['online'])
