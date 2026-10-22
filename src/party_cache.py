"""Small atomic restart checkpoint; no coordinates or raw reconnect secrets."""
import json
import math
import os
from pathlib import Path
import re
import time
from map_catalog import DIFFICULTIES, layouts_for
from party_protocol import COLORS, username

ROOM_FIELDS = ('code','difficulty','epoch','revision','layout','confidence','source','host','started_by')
MEMBER_FIELDS = ('id','username','color','token_hash')


class PartyCache:
    def __init__(self, path):
        self.path = Path(path)

    def snapshot(self, rooms):
        wall, mono = time.time(), time.monotonic()
        records = []
        for room in rooms.values():
            members = []
            for member in room['members'].values():
                remaining = 60 if member['socket'] is not None else 60-(mono-member['disconnected'])
                if remaining <= 0:continue
                members.append(dict({k:member[k] for k in MEMBER_FIELDS}, expires=wall+remaining))
            if members:
                records.append(dict({k:room.get(k) for k in ROOM_FIELDS}, members=members))
        return dict(version=1, rooms=records)

    def save(self, snapshot):
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        temporary = self.path.with_suffix('.tmp')
        try:
            descriptor = os.open(temporary, os.O_WRONLY|os.O_CREAT|os.O_TRUNC, 0o600)
            with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
                json.dump(snapshot, stream, separators=(',', ':'), allow_nan=False)
                stream.flush();os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        finally:
            temporary.unlink(missing_ok=True)

    def load(self, limit):
        if not self.path.exists():return []
        if self.path.stat().st_size > 8*1024*1024:raise ValueError('cache_too_large')
        data = json.loads(self.path.read_text(encoding='utf-8'))
        if data['version'] != 1 or not isinstance(data['rooms'], list) or len(data['rooms']) > limit:
            raise ValueError('invalid_cache')
        restored, codes = [], set()
        now = time.time()
        for record in data['rooms']:
            code, difficulty = record['code'], record['difficulty']
            if not isinstance(code,str) or not re.fullmatch(r'[A-Z2-9]{8}',code) or code in codes:
                raise ValueError('invalid_cache')
            codes.add(code)
            if difficulty not in DIFFICULTIES:raise ValueError('invalid_cache')
            for field, minimum in (('epoch',1),('revision',0)):
                if type(record[field]) is not int or not minimum <= record[field] < 2**53:raise ValueError('invalid_cache')
            layout, score = record['layout'], record['confidence']
            if (layout is not None and (type(layout) is not int or layout not in layouts_for(difficulty)) or
                    type(score) not in (int,float) or not math.isfinite(score) or not 0<=score<=1):
                raise ValueError('invalid_cache')
            if ((layout is None and (score!=0 or record['source'] is not None)) or
                    (layout is not None and (score<.75 or record['source'] is None or record['revision']<1))):
                raise ValueError('invalid_cache')
            for field in ('host','source','started_by'):
                value=record.get(field)
                if value is not None and (not isinstance(value,str) or not re.fullmatch(r'[0-9a-f]{16}',value)):
                    raise ValueError('invalid_cache')
            if not isinstance(record['members'],list) or not 1<=len(record['members'])<=3:raise ValueError('invalid_cache')
            members, identities, colors = [], set(), set()
            for member in record['members']:
                identity, color, digest = member['id'], member['color'], member['token_hash']
                if (not isinstance(identity,str) or not re.fullmatch(r'[0-9a-f]{16}',identity) or identity in identities or
                        color not in COLORS or color in colors or not isinstance(digest,str) or not re.fullmatch(r'[0-9a-f]{64}',digest)):
                    raise ValueError('invalid_cache')
                identities.add(identity);colors.add(color)
                expires=member['expires']
                if type(expires) not in (int,float) or not math.isfinite(expires):raise ValueError('invalid_cache')
                name=username(member['username'])
                if expires>now:
                    members.append(dict(id=identity,username=name,color=color,token_hash=digest,
                                        remaining=min(60,expires-now)))
            if members:restored.append(dict({k:record.get(k) for k in ROOM_FIELDS},members=members))
        return restored
