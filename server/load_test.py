"""Exercise a separate relay instance using real, active three-member parties."""
import argparse
import asyncio
from collections import deque
import json
import random
import statistics
import time
from websockets.asyncio.client import connect


async def run(url, players, duration):
    if players < 3 or players % 3: raise ValueError('players must be a positive multiple of 3')
    sockets=[];readers=[];senders=[];sent={};latencies=deque(maxlen=100000)
    counts=dict(frames=0,bytes=0,updates=0,disconnects=0,position_frames=0)
    semaphore=asyncio.Semaphore(30)
    stop=asyncio.Event()

    async def reader(socket):
        last_seen={}
        try:
            async for raw in socket:
                counts['frames']+=1;counts['bytes']+=len(raw.encode('utf-8'))
                message=json.loads(raw)
                if message['type']=='error':raise RuntimeError(message['code'])
                if message['type']=='positions':
                    counts['position_frames']+=1
                    positions=message['positions']
                elif message['type']=='state':
                    positions=[(p['id'],p['position'],p['age']) for p in message['state']['members']]
                else:continue
                for identity,point,_ in positions:
                    if point is not None and (identity,point[0]) in sent and last_seen.get(identity)!=point[0]:
                        last_seen[identity]=point[0]
                        latencies.append((time.monotonic()-sent[identity,point[0]])*1000)
        except Exception:
            if not stop.is_set():counts['disconnects']+=1

    async def join(message):
        socket=await connect(url,compression=None,proxy=None,max_size=8192,max_queue=2,open_timeout=20)
        sockets.append(socket)
        await socket.send(json.dumps(message))
        welcome=json.loads(await asyncio.wait_for(socket.recv(),10))
        if welcome.get('type')!='welcome':raise RuntimeError(welcome)
        readers.append(asyncio.create_task(reader(socket)))
        return socket,welcome

    async def room(index):
        async with semaphore:
            host,first=await join(dict(type='create',username=f'Load{index}-A',difficulty='Chaos'))
            members=[(host,first['id'])]
            for suffix in ('B','C'):
                socket,welcome=await join(dict(type='join',username=f'Load{index}-{suffix}',code=first['state']['code']))
                members.append((socket,welcome['id']))
            await host.send(json.dumps(dict(type='update',epoch=1,evidence=dict(layout=32,confidence=.9))))
            return members

    async def sender(socket,identity):
        await asyncio.sleep(random.random()*.5)
        sequence=0
        try:
            while not stop.is_set():
                sequence=(sequence+1)%100
                sent[identity,sequence]=time.monotonic()
                await socket.send(json.dumps(dict(type='update',epoch=1,revision=1,layout=32,position=[sequence,50]),separators=(',',':')))
                counts['updates']+=1
                await asyncio.sleep(.5)
        except Exception:
            if not stop.is_set():counts['disconnects']+=1

    started=time.monotonic()
    try:
        rooms=await asyncio.gather(*(room(i) for i in range(players//3)))
        connected_seconds=time.monotonic()-started
        await asyncio.sleep(.5)
        for members in rooms:
            for socket,identity in members:senders.append(asyncio.create_task(sender(socket,identity)))
        traffic_start=time.monotonic();await asyncio.sleep(duration);elapsed=time.monotonic()-traffic_start
        result=dict(players=players,rooms=players//3,connect_seconds=round(connected_seconds,2),
                    active_seconds=round(elapsed,2),**counts,
                    received_mib_per_second=round(counts['bytes']/elapsed/1048576,3),
                    latency_p50_ms=round(statistics.median(latencies),1) if latencies else None,
                    latency_p95_ms=round(sorted(latencies)[int(len(latencies)*.95)],1) if latencies else None,
                    latency_max_ms=round(max(latencies),1) if latencies else None)
        print(json.dumps(result,indent=2),flush=True)
        if counts['disconnects'] or counts['updates']==0 or not latencies:raise RuntimeError('Load test did not complete cleanly')
    finally:
        stop.set()
        for task in senders:task.cancel()
        await asyncio.gather(*senders,return_exceptions=True)
        await asyncio.gather(*(socket.send('{"type":"leave"}') for socket in sockets),return_exceptions=True)
        await asyncio.gather(*(socket.close() for socket in sockets),return_exceptions=True)
        await asyncio.gather(*readers,return_exceptions=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url',default='ws://127.0.0.1:8787/party')
    parser.add_argument('--players',type=int,default=300)
    parser.add_argument('--seconds',type=float,default=15)
    args=parser.parse_args()
    asyncio.run(run(args.url,args.players,args.seconds))
