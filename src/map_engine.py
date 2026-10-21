from asset_paths import ASSETS
"""Offline floor plans, key-room routes and screen-only map registration."""
import json
import math
from functools import lru_cache
from pathlib import Path
import numpy as np
import cv2
from PIL import Image,ImageDraw,ImageOps
from map_catalog import layouts_for
from i18n import tr

SIMULATOR=ASSETS/'simulator'


class MapLibrary:
    def __init__(self,difficulty='Chaos'):
        self.models={};self.difficulty=difficulty

    def model(self,layout):
        if layout not in self.models:self.models[layout]=MapEngine(layout)
        return self.models[layout]

    def identify(self,frame,region=None):
        if not (SIMULATOR/f'layout-{layouts_for(self.difficulty)[0]}.json').exists():return None
        matches=[]
        for layout in layouts_for(self.difficulty):
            result=self.model(layout).match_minimap(frame,region)
            if result:matches.append(dict(result,layout=layout))
        # Repeated rooms can match more than one floor plan. Wait for a new
        # corridor view rather than breaking that tie with a small score gap.
        return matches[0] if len(matches)==1 else None


class MapEngine:
    def __init__(self,layout):
        cv2.setNumThreads(2)
        self.layout=int(layout)
        self.data=json.loads((SIMULATOR/f'layout-{layout}.json').read_text(encoding='utf-8'))
        self.routes=json.loads((SIMULATOR/f'route-{layout}.json').read_text(encoding='utf-8'))
        self.image=Image.open(SIMULATOR/f'assets/lost-sanctum/maps/200{layout}-full.webp').convert('RGB')
        self.sift=cv2.SIFT_create(nfeatures=1800,contrastThreshold=.015)
        # The game floor texture is used for recognition; the annotated render is
        # used for display. Both versions share the same room geometry.
        legacy=ASSETS/f'map-{layout}.webp'
        self.reference=Image.open(legacy).convert('RGB') if legacy.exists() else self.image.copy()
        self.ref_gray=self._gray(self.reference)
        self.kp,self.desc=self.sift.detectAndCompute(self.ref_gray,None)
        self.points=None
        self.floor_scale=min(500/self.reference.width,500/self.reference.height)
        fit=ImageOps.contain(self.reference,(500,500),Image.Resampling.NEAREST)
        self.floor_offset=np.array([(500-fit.width)//2,(500-fit.height)//2])
        small=Image.new('RGB',(500,500));small.paste(fit,tuple(self.floor_offset))
        self.floor=self._floor(small,110)
        self.geometry_scale=None
        self._minimap_area=None
        self._minimap_frame_size=None
        self._minimap_misses=0

    @staticmethod
    def _floor(image,threshold):
        hsv=cv2.cvtColor(np.asarray(image.convert('RGB')),cv2.COLOR_RGB2HSV)
        return (cv2.inRange(hsv,np.array([0,0,threshold]),np.array([180,85,255]))/255).astype(np.float32)

    def _reference_position(self,q):
        anchors=json.loads((ASSETS/'maps.json').read_text()).get(str(self.layout))
        if anchors is None:
            anchors={name:[self.data['doors'][door]['x']/100,self.data['doors'][door]['y']/100]
                     for name,door in [('orange','main'),('blue','side')]}
        ra=np.array(anchors['orange'])*np.array(self.reference.size)
        rb=np.array(anchors['blue'])*np.array(self.reference.size)
        return self.position_from_map({'orange':ra,'blue':rb,'player':q})

    @staticmethod
    def _gray(image):
        gray=cv2.cvtColor(np.asarray(image.convert('RGB')),cv2.COLOR_RGB2GRAY)
        return cv2.createCLAHE(2.,(8,8)).apply(gray)

    def position_from_map(self,reading):
        if not all(k in reading for k in ('orange','blue','player')):return None
        a,b,p=(np.array(reading[k],float) for k in ('orange','blue','player'))
        doors=self.data['doors']
        qa=np.array([doors['main']['x'],doors['main']['y']])*np.array(self.image.size)/100
        qb=np.array([doors['side']['x'],doors['side']['y']])*np.array(self.image.size)/100
        d=b-a;e=qb-qa;den=d@d
        if den<400:return None
        re,im=(e@d)/den,(e[1]*d[0]-e[0]*d[1])/den
        x,y=p-a
        q=qa+np.array([re*x-im*y,im*x+re*y])
        return [float(q[0]/self.image.width*100),float(q[1]/self.image.height*100)]

    @lru_cache(maxsize=96)
    def route(self,entrance=0,keys=2,goal='keys',eggs=1,rooms=1,exit='nearest'):
        if goal not in ('keys','eggs','both','none','rich','trials'):raise ValueError('Unknown route goal')
        if exit not in ('nearest','orange','blue'):raise ValueError('Unknown exit')
        pts=self.routes['pts'];dist=self.routes['D']
        wanted={'key':max(0,min(3,int(keys))) if goal in ('keys','both') else 0,
                'nest':max(0,min(8,int(eggs))) if goal in ('eggs','both') else 0,
                'room':max(0,min(4,int(rooms))) if goal=='rich' else 0,
                'challenge':max(0,min(4,int(rooms))) if goal=='trials' else 0}
        for kind in wanted:wanted[kind]=min(wanted[kind],sum(p['k']==kind for p in pts))
        targets=[i for i,p in enumerate(pts) if wanted.get(p['k'],0)]
        masks={kind:sum(1<<j for j,i in enumerate(targets) if pts[i]['k']==kind) for kind in wanted}
        # Cheapest visit order per subset/end point; bounds prevent factorial
        # work when a user requests multiple nests or rich rooms.
        states={(0,int(entrance)):(0.,())}
        for _ in range(sum(wanted.values())):
            following={}
            for (mask,last),(cost,order) in states.items():
                counts={kind:(mask&bits).bit_count() for kind,bits in masks.items()}
                for j,index in enumerate(targets):
                    if mask&(1<<j) or counts[pts[index]['k']]>=wanted[pts[index]['k']]:continue
                    distance=dist[last][index]
                    if distance is None:continue
                    state=(mask|(1<<j),index);value=cost+distance
                    if state not in following or value<following[state][0]:following[state]=(value,order+(index,))
            states=following
        best=None
        for (_,last),(cost,order) in states.items():
            for end in ((0,1) if exit=='nearest' else (0,) if exit=='orange' else (1,)):
                distance=0 if last==end else dist[last][end]
                if distance is None:continue
                candidate=(cost+distance,(int(entrance),)+order+(end,))
                if best is None or candidate[0]<best[0]:best=candidate
        if best is None:raise ValueError('No connected route satisfies these targets')
        segments=[]
        for a,b in zip(best[1],best[1][1:]):
            if a==b:continue
            lo,hi=sorted((a,b));parts=self.routes['P'].get(f'{lo}-{hi}',[])
            segments.extend(parts if a<b else [list(reversed(p)) for p in reversed(parts)])
        return dict(distance=best[0],stops=[pts[i] for i in best[1]],segments=segments)

    def match_minimap(self,frame,region=None,previous=None):
        """Return a position only after geometric registration; never dead-reckon."""
        # An accepted registration establishes the HUD bounds too. Reuse only
        # those bounds; every frame still passes the same geometric and player
        # validation. Explicit user calibration always takes precedence.
        if region is not None:
            return self._match_minimap(frame,region,previous)
        if self._minimap_frame_size!=frame.size:
            self._minimap_area=None
            self._minimap_misses=0
            self._minimap_frame_size=frame.size
        if self._minimap_area is not None:
            result=self._match_minimap(frame,self._minimap_area,previous)
            if result:
                self._minimap_misses=0
                return result
            self._minimap_misses+=1
            if self._minimap_misses<2:return None
            self._minimap_area=None
        result=self._match_minimap(frame,None,previous)
        if result:
            w,h=frame.size
            self._minimap_area=[n/scale for n,scale in zip(result['region'],(w,h,w,h))]
            self._minimap_misses=0
        return result

    def _match_minimap(self,frame,region=None,previous=None):
        w,h=frame.size
        boxes=[tuple(round(n*s) for n,s in zip(region,(w,h,w,h)))] if region else []
        if not region:
            # Actual Sanctum footage has a circular, north-up minimap at the
            # top left. Scenery/HUD outside its rim must never enter matching.
            corner=np.asarray(frame.crop((0,0,round(w*.30),round(h*.48))))
            gray=cv2.cvtColor(corner,cv2.COLOR_RGB2GRAY)
            circles=cv2.HoughCircles(cv2.GaussianBlur(gray,(5,5),1),cv2.HOUGH_GRADIENT,1.2,35,
                param1=90,param2=26,minRadius=max(28,round(h*.045)),maxRadius=round(h*.15))
            if circles is not None:
                ranked=sorted(circles[0],key=lambda p:((p[0]/w-.095)**2+(p[1]/h-.13)**2+(p[2]/h-.09)**2))
                for x,y,r in ranked[:1]:
                    if x-r<0 or y-r<0:continue
                    boxes.append((round(x-r),round(y-r),round(x+r),round(y+r)))
        best=None
        for box in boxes:
            crop=frame.crop(box);gray=self._gray(crop)
            circle=np.zeros(gray.shape,np.uint8)
            center=(gray.shape[1]//2,gray.shape[0]//2)
            radius=round(min(gray.shape)*.46)
            cv2.circle(circle,center,radius,255,-1)
            kp,desc=self.sift.detectAndCompute(gray,circle)
            if desc is None or self.desc is None:continue
            pairs=cv2.BFMatcher().knnMatch(desc,self.desc,k=2)
            matches=[a for a,b in pairs if a.distance<.68*b.distance]
            if len(matches)<9:continue
            src=np.float32([kp[m.queryIdx].pt for m in matches])
            dst=np.float32([self.kp[m.trainIdx].pt for m in matches])
            matrix,mask=cv2.estimateAffinePartial2D(src,dst,method=cv2.RANSAC,ransacReprojThreshold=3,maxIters=1500)
            if matrix is None:continue
            count=int(mask.sum());spread=np.ptp(src[mask.ravel()==1],axis=0)
            scale=math.hypot(matrix[0,0],matrix[0,1])
            if count<8 or count/len(matches)<.55 or min(spread)<24 or not .2<scale<12:continue
            hsv=cv2.cvtColor(np.asarray(crop),cv2.COLOR_RGB2HSV)
            yellow=cv2.inRange(hsv,np.array([18,95,170]),np.array([42,255,255]))
            n,labels,stats,centers=cv2.connectedComponentsWithStats(yellow)
            arrows=[(stats[i,cv2.CC_STAT_AREA],centers[i]) for i in range(1,n)
                    if 12<stats[i,cv2.CC_STAT_AREA]<1500 and 5<stats[i,cv2.CC_STAT_WIDTH]<50
                    and 5<stats[i,cv2.CC_STAT_HEIGHT]<50]
            if not arrows:continue
            # Select the gold player arrow closest to the center of the
            # geometrically matched map patch, excluding peripheral HUD labels.
            mid=np.array(center)
            arrows=[a for a in arrows if np.linalg.norm(a[1]-mid)<radius*.3]
            if not arrows:continue
            point=min(arrows,key=lambda a:np.linalg.norm(a[1]-mid))[1]
            q=matrix@np.array([point[0],point[1],1.])
            if not (0<=q[0]<self.reference.width and 0<=q[1]<self.reference.height):continue
            # MOANIIMO and the route render use different crop bounds. Align via
            # their two portal anchors to place this registered point correctly.
            position=self._reference_position(q)
            if previous is not None and math.dist(position,previous)>12:continue
            result=dict(player=position,inliers=count,region=list(box))
            if best is None or count>best['inliers']:best=result
        return best or self._geometry_match(frame,boxes,previous)

    def _geometry_match(self,frame,boxes,previous):
        """Masked corridor correlation tolerates carrying-egg/waypoint icons.

        A minimap centers the player even when its marker changes. Only the
        circular interior is sampled; center markers and top labels are masked.
        """
        peaks=[]
        for box in boxes:
            crop=frame.crop(box)
            side=min(crop.size)
            if side<60:continue
            binary=self._floor(crop,110)
            mask=np.zeros(binary.shape,np.uint8)
            center=(binary.shape[1]//2,binary.shape[0]//2)
            cv2.circle(mask,center,round(side*.445),1,-1)
            cv2.circle(mask,center,round(side*.11),0,-1)
            cv2.rectangle(mask,(round(side*.20),0),(round(side*.53),round(side*.21)),0,-1)
            # Suppress colored waypoints/party icons, wherever the user pins them.
            hsv=cv2.cvtColor(np.asarray(crop),cv2.COLOR_RGB2HSV)
            mask[(hsv[:,:,1]>100)&(hsv[:,:,2]>130)]=0
            scales=np.linspace(self.geometry_scale*.92,self.geometry_scale*1.08,11) if self.geometry_scale else np.geomspace(.25,2.6,43)
            for scale in scales:
                width,height=round(crop.width*scale),round(crop.height*scale)
                if min(width,height)<25 or max(width,height)>450:continue
                t=cv2.resize(binary,(width,height),interpolation=cv2.INTER_NEAREST)
                m=cv2.resize(mask,(width,height),interpolation=cv2.INTER_NEAREST).astype(np.float32)
                n=m.sum();st=(t*m).sum();vt=st-st*st/max(n,1)
                if n<100 or vt<n*.025:continue
                sr=cv2.matchTemplate(self.floor,m,cv2.TM_CCORR)
                srt=cv2.matchTemplate(self.floor,t*m,cv2.TM_CCORR)
                vr=sr-sr*sr/n
                scores=(srt-sr*st/n)/np.sqrt(np.maximum(vr*vt,1e-8))
                scores[(~np.isfinite(scores))|(vr<n*.025)]=-1
                _,score,_,point=cv2.minMaxLoc(scores)
                q=np.array([point[0]+width/2,point[1]+height/2])
                peaks.append((score,q,box,scale))
                # A second distant room at the same scale is an ambiguity too.
                cv2.circle(scores,point,45,-1,-1)
                _,second,_,p2=cv2.minMaxLoc(scores)
                peaks.append((second,np.array([p2[0]+width/2,p2[1]+height/2]),box,scale))
        if not peaks:return None
        peaks.sort(key=lambda p:p[0],reverse=True)
        score,q,box,scale=peaks[0]
        alternative=max((p[0] for p in peaks if np.linalg.norm(p[1]-q)>40),default=-1)
        if score<.73 or score-alternative<.045:
            self.geometry_scale=None
            return None
        position=self._reference_position((q-self.floor_offset)/self.floor_scale)
        if previous is not None and math.dist(position,previous)>12:return None
        self.geometry_scale=scale
        return dict(player=position,confidence=float(score),method='corridors',region=list(box),inliers=0)

    def render(self,size=(700,700),keys=2,entrance=None,player=None,zoom=1.,follow=True,live=False,goal='keys',eggs=1,icons=None,unconfirmed_trials=False,teammates=None,player_name=None,player_color='#3df5ff',rooms=1,exit='nearest',legend=False):
        # All marker/route coordinates refer to the original render percentages.
        im=self.image.copy();draw=ImageDraw.Draw(im)
        def xy(p):return (p[0]*im.width/100,p[1]*im.height/100)
        icons={**dict(keys=True,eggs=True,trials=True,chests=True,monsters=False),**(icons or {})}
        # Independent alternatives, each satisfying the full requested goal.
        # Blue dashes leave the orange path visible wherever the routes overlap.
        for start in ((0,1) if entrance is None else (entrance,)):
            color=('#ff9b43','#65b5ff')[start]
            width=max(5,im.width//180)
            for segment in self.route(start,keys,goal,eggs,rooms,exit)['segments']:
                points=[xy(p) for p in segment]
                if len(points)<2:continue
                if start==0:draw.line(points,fill=color,width=width,joint='curve')
                else:
                    phase=0.;dash=width*2.5;period=dash*1.7
                    for a,b in zip(points,points[1:]):
                        length=math.dist(a,b)
                        cursor=0.
                        while cursor<length:
                            step=min(length-cursor,(dash if phase<dash else period)-phase)
                            if phase<dash:
                                draw.line([(a[0]+(b[0]-a[0])*t/length,a[1]+(b[1]-a[1])*t/length) for t in (cursor,cursor+step)],fill=color,width=width)
                            cursor+=step;phase=(phase+step)%period
        for name,color in [('main','#ff9b43'),('side','#65b5ff')]:
            p=self.data['doors'][name];x,y=xy([p['x'],p['y']]);draw.rectangle((x-10,y-10,x+10,y+10),fill=color,outline='white',width=2)
        scale=min(size[0]/im.width,size[1]/im.height)*zoom
        scaled=im.resize((round(im.width*scale),round(im.height*scale)),Image.Resampling.LANCZOS)
        canvas=Image.new('RGB',size,(0,0,1))
        center=xy(player) if player and follow and zoom>1 else (im.width/2,im.height/2)
        offset=(round(size[0]/2-center[0]*scale),round(size[1]/2-center[1]*scale))
        canvas.paste(scaled,offset)
        # Draw room symbols after scaling so they remain readable on the overlay.
        groups=[('nests','egg','eggs'),('keyrooms','key','keys'),('challenges','trial','trials'),('rooms','chest','chests'),('mobs','monster','monsters')]
        for name,kind,category in groups:
            if not icons[category]:continue
            icon=room_icon(kind)
            for p in self.data[name]:
                if kind=='trial' and p.get('maybe') and not unconfirmed_trials:continue
                if kind=='chest' and not any(p.get(c,0)>0 for c in ('gold','purple','blue')):continue
                x,y=xy([p['x'],p['y']])
                x,y=round(x*scale+offset[0]),round(y*scale+offset[1])
                canvas.paste(icon,(x-icon.width//2,y-icon.height//2),icon)
                if kind=='trial' and p.get('maybe'):
                    ImageDraw.Draw(canvas).text((x+8,y-19),'?',fill='#ffc65c',stroke_width=1,stroke_fill='#15232f')
        markers=list(teammates or [])
        if player:markers.append(dict(position=player,name=player_name or tr('YOU'),color=player_color,live=live))
        for marker in markers:
            x,y=xy(marker['position'])
            x,y=round(x*scale+offset[0]),round(y*scale+offset[1])
            draw=ImageDraw.Draw(canvas)
            color=marker['color']
            # Fixed screen size and a dark halo keep YOU distinct from the route,
            # even when the whole map is scaled down or a room icon overlaps it.
            draw.ellipse((x-20,y-20,x+20,y+20),fill='#14232f',outline=color,width=3)
            for a,b in [((x-27,y),(x-19,y)),((x+19,y),(x+27,y)),((x,y-27),(x,y-19)),((x,y+19),(x,y+27))]:
                draw.line((a,b),fill=color,width=3)
            draw.ellipse((x-10,y-10,x+10,y+10),fill=color if marker['live'] else '#8f9caa',outline='white',width=2)
            label=marker['name']+('' if marker['live'] else ' · '+tr('last known'))
            bounds=draw.textbbox((0,0),label)
            width=bounds[2]-bounds[0]
            draw.rounded_rectangle((x-width//2-5,y+28,x+width//2+6,y+45),radius=4,fill='#14232f',outline=color)
            draw.text((x-width//2,y+30),label,fill='white')
        if legend:
            draw=ImageDraw.Draw(canvas)
            rows=[('key','Key doors'),('egg','Egg nests'),('trial','Sanctums / trials'),('chest','Chest rooms'),('monster','Monsters')]
            y=max(4,size[1]-len(rows)*27-14)
            draw.rounded_rectangle((8,y-5,174,size[1]-7),radius=6,fill='#14232f',outline='#536783')
            for kind,label in rows:
                icon=room_icon(kind);canvas.paste(icon,(12,y),icon)
                draw.text((46,y+7),tr(label),fill='white');y+=27
        pixels=np.asarray(canvas).copy()
        pixels[np.max(pixels,axis=2)<22]=(0,0,1)
        return Image.fromarray(pixels)


@lru_cache(maxsize=5)
def room_icon(kind):
    """Font-independent room symbols, drawn at 2x for small overlay sizes."""
    icon=Image.new('RGBA',(64,64))
    d=ImageDraw.Draw(icon)
    d.ellipse((2,2,62,62),fill='#15232f',outline={'key':'#ffcb54','egg':'#eeb6ff','trial':'#87bcff','chest':'#e7b56b','monster':'#ff8f9c'}[kind],width=3)
    if kind=='key':
        d.line((27,28,47,48),fill='#ffdc73',width=8)
        d.line((39,39,45,33),fill='#ffdc73',width=7)
        d.line((46,46,52,40),fill='#ffdc73',width=7)
        d.ellipse((11,10,33,32),fill='#ffdc73')
        d.ellipse((17,16,27,26),fill='#15232f')
    elif kind=='trial':
        d.polygon([(32,11),(14,28),(32,52),(50,28)],fill='#8ebeff',outline='white',width=3)
        d.line((32,19,32,42),fill='#15232f',width=4)
        d.line((23,29,41,29),fill='#15232f',width=4)
    elif kind=='monster':
        d.polygon([(14,18),(23,23),(32,17),(41,23),(50,18),(48,41),(39,50),(25,50),(16,41)],fill='#ff8f9c')
        d.ellipse((22,29,27,35),fill='#15232f');d.ellipse((37,29,42,35),fill='#15232f')
    elif kind=='chest':
        d.rounded_rectangle((13,22,51,49),radius=4,fill='#e7b56b',outline='#fff0bd',width=3)
        d.line((14,32,50,32),fill='#15232f',width=4)
        d.rectangle((28,28,36,38),fill='#fff0bd')
    else:
        d.polygon([(32,10),(24,14),(17,28),(15,41),(19,50),(28,54),(36,54),(45,50),(49,41),(47,28),(40,14)],fill='#fff2fc')
        d.ellipse((22,28,29,37),fill='#c98cdd')
        d.ellipse((35,39,43,47),fill='#c98cdd')
        d.ellipse((32,18,37,23),fill='#e7bbf4')
    return icon.resize((28,28),Image.Resampling.LANCZOS)
