"""Bounded local paths; missing observations never connect separate journeys."""
from collections import OrderedDict,deque
import math


class PlayerTrails:
    def __init__(self,limit=600):
        self.limit=limit;self.context=None;self.players=OrderedDict()

    def reset(self,context):
        if self.context==context:return False
        self.context=context;self.players.clear();return True

    def retain(self,identities):
        for identity in list(self.players):
            if identity not in identities:del self.players[identity]

    def observe(self,identity,color,point,now):
        if point is None:
            if identity in self.players:self.players[identity]['last']=None
            return False
        if len(point)!=2 or not all(math.isfinite(n) and 0<=n<=100 for n in point):return False
        point=tuple(point)
        if identity not in self.players:
            self.players[identity]=dict(color=color,points=deque(maxlen=self.limit),last=None,time=now)
            while len(self.players)>3:self.players.popitem(last=False)
        entry=self.players[identity];last=entry['last']
        continuous=last is not None and now-entry['time']<3 and math.dist(last,point)<=12
        entry['time']=now
        if continuous and math.dist(last,point)<.4:return False
        if not continuous and entry['points'] and entry['points'][-1] is not None:entry['points'].append(None)
        entry['points'].append(point);entry['last']=point
        return True

    def paths(self):
        result=[]
        for entry in self.players.values():
            segments=[];part=[]
            for point in entry['points']:
                if point is None:
                    if part:segments.append(part)
                    part=[]
                else:part.append(point)
            if part:segments.append(part)
            if segments:result.append(dict(color=entry['color'],segments=segments))
        return result
