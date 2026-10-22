"""Local corridor recognition; no capture, downloads, ledger or UI side effects.

Independent Python implementation of floor/wall correlation and temporal evidence,
inspired by MOANIIMO's browser finder. See THIRD_PARTY_NOTICES.md.
"""
import math
import time
from pathlib import Path

import cv2
import numpy as np
from PIL import Image


def visible_minimap(frame,box):
    """Require a current circular HUD rim, including for cached/manual areas.

    Sample radial edges rather than repeating Hough search on every frame.
    Map texture or menu tiles inside a saved rectangle are not HUD evidence.
    """
    left,top,right,bottom=box
    radius=min(right-left,bottom-top)/2
    if radius<20:return False
    center=((left+right)/2,(top+bottom)/2)
    angles=np.linspace(0,2*np.pi,64,endpoint=False)
    radii=np.linspace(.90,1.08,19)*radius
    xs=np.rint(center[0]+radii[:,None]*np.cos(angles)).astype(int)
    ys=np.rint(center[1]+radii[:,None]*np.sin(angles)).astype(int)
    if xs.min()<0 or ys.min()<0 or xs.max()>=frame.width or ys.max()>=frame.height:return False
    x0,y0,x1,y1=int(xs.min()),int(ys.min()),int(xs.max()+1),int(ys.max()+1)
    pixels=np.asarray(frame.crop((x0,y0,x1,y1)).convert('RGB'))
    values=pixels[ys-y0,xs-x0].mean(axis=2)
    edges=np.abs(np.diff(values,axis=0))>=12
    return any(np.any(edges[i:i+3],axis=0).mean()>=.55 for i in range(len(edges)-2))


class MinimapRecognizer:
    """Observe game frames and return missing/outside/searching/match evidence.

    References are unannotated north-up floor plans, not route renders. Only
    compact floor masks are retained. A match needs a unique layout AND position
    over three spaced observations; a screenshot or repeated room cannot confirm
    a layout by itself. The instance belongs to one navigation context.
    """
    def __init__(self,references,outdoor=None):
        cv2.setNumThreads(2)
        self.references=references
        self.outdoor=outdoor
        self.outdoor_pixels=None
        self.floors={}
        self.evidence={}
        self.last_layout=None
        self.last_position=None
        self.last_time=None
        self.streak=0
        self.frame_size=None

    @classmethod
    def from_assets(cls,folder,layouts):
        folder=Path(folder)
        paths={layout:folder/f'map-{layout}.webp' for layout in layouts}
        outdoor=folder/'outdoor-minimap.webp'
        # Older packs can still use M; do not silently omit the outdoor guard.
        if not outdoor.is_file() or not all(path.is_file() for path in paths.values()):return None
        return cls(paths,outdoor)

    @staticmethod
    def _image(value):
        if isinstance(value,Image.Image):return np.asarray(value.convert('RGB'))
        with Image.open(value) as image:return np.asarray(image.convert('RGB'))

    def _load(self):
        if self.floors:return
        floors={}
        for layout,value in self.references.items():
            pixels=self._image(value).astype(np.float32)
            gray=pixels.mean(axis=2)
            floor=((gray>140)&(gray<240)).astype(np.float32)
            floors[layout]=cv2.resize(floor,(230,230),interpolation=cv2.INTER_AREA)
        self.floors=floors

    def _outside(self,patch):
        pixels=np.asarray(patch.convert('RGB')).astype(np.float32)
        height,width=pixels.shape[:2]
        yy,xx=np.ogrid[:height,:width]
        distance=((xx-width/2)/(width/2))**2+((yy-height/2)/(height/2))**2
        mask=(distance<.84**2)&(distance>.23**2)
        green=(pixels[:,:,1]>pixels[:,:,0]+8)&(pixels[:,:,1]>pixels[:,:,2]+5)&(np.ptp(pixels,axis=2)>20)
        if (green&mask).sum()/max(1,mask.sum())>.10:return True
        # Party labels and pinned waypoints are not island texture. Keeping
        # their bright colors in RGB comparison can hide an outdoor match.
        icons=(np.ptp(pixels,axis=2)>90)&(pixels.max(axis=2)>170)
        mask &= ~icons
        if self.outdoor is None:return False
        if self.outdoor_pixels is None:
            reference=self._image(self.outdoor).astype(np.float32)
            self.outdoor_pixels=cv2.resize(reference,(360,round(reference.shape[0]*360/reference.shape[1])),interpolation=cv2.INTER_AREA)
        reference=self.outdoor_pixels
        ref_gray=reference.mean(axis=2)
        # Outdoor geometry may resemble stone dungeon corridors. Compare RGB
        # texture against the island itself, across HUD scales, before accepting.
        for side in np.geomspace(8,84,16).round().astype(int):
            template=cv2.resize(pixels,(side,side),interpolation=cv2.INTER_AREA)
            m=cv2.resize(mask.astype(np.uint8),(side,side),interpolation=cv2.INTER_NEAREST)>0
            if m.sum()<20 or template[m>0].std()<12:continue
            known=template[m]
            centered=known-known.mean(axis=0)
            norm=float(np.linalg.norm(centered))
            if norm<1:continue
            coarse=template.mean(axis=2)
            coarse[~m]=float(known.mean())
            scores=cv2.matchTemplate(ref_gray,coarse,cv2.TM_CCOEFF_NORMED)
            for _ in range(3):
                _,score,_,(x,y)=cv2.minMaxLoc(scores)
                if score<.5:break
                candidate=reference[y:y+side,x:x+side][m]
                candidate=candidate-candidate.mean(axis=0)
                agreement=float((candidate*centered).sum())/max(1,float(np.linalg.norm(candidate))*norm)
                if agreement>.94:return True
                cv2.circle(scores,(x,y),max(2,side//4),-1,-1)
        return False

    def _box(self,frame,region):
        width,height=frame.size
        if region is not None:
            box=tuple(round(v*s) for v,s in zip(region,(width,height,width,height)))
            return box if 0<=box[0]<box[2]<=width and 0<=box[1]<box[3]<=height else None
        # Search one small, normalized HUD corner rather than all game pixels.
        scale=min(1,720/height)
        image=np.asarray(frame.crop((0,0,round(width*.3),round(height*.35))).convert('RGB'))
        image=cv2.resize(image,None,fx=scale,fy=scale)
        gray=cv2.cvtColor(image,cv2.COLOR_RGB2GRAY)
        circles=cv2.HoughCircles(cv2.GaussianBlur(gray,(5,5),1),cv2.HOUGH_GRADIENT,1.2,30,
            param1=90,param2=26,minRadius=max(20,round(height*scale*.045)),maxRadius=round(height*scale*.15))
        if circles is None:return None
        x,y,r=min(circles[0],key=lambda p:(p[0]/(width*scale)-.095)**2+(p[1]/(height*scale)-.13)**2)
        box=tuple(round(v/scale) for v in (x-r,y-r,x+r,y+r))
        return box if 0<=box[0]<box[2]<=width and 0<=box[1]<box[3]<=height else None

    @staticmethod
    def _template(patch):
        pixels=np.asarray(patch.convert('RGB')).astype(np.float32)
        height,width=pixels.shape[:2]
        yy,xx=np.ogrid[:height,:width]
        distance=((xx-width/2)/(width/2))**2+((yy-height/2)/(height/2))**2
        mask=(distance<.86**2)&(distance>.20**2)
        gray=pixels.mean(axis=2)
        chroma=np.ptp(pixels,axis=2)
        floor=(chroma<42)&(gray>155)&(gray<240)
        wall=(gray<115)&(chroma<65)
        green=(pixels[:,:,1]>pixels[:,:,0]+8)&(pixels[:,:,1]>pixels[:,:,2]+5)&(chroma>20)
        n=max(1,mask.sum())
        fraction=(floor&mask).sum()/n
        if not .05<fraction<.80 or (green&mask).sum()/n>.10:return None
        f=cv2.resize((floor&mask).astype(np.float32),(37,37),interpolation=cv2.INTER_AREA)
        w=cv2.resize((wall&mask).astype(np.float32),(37,37),interpolation=cv2.INTER_AREA)
        edge=cv2.dilate((w>.5).astype(np.uint8),np.ones((3,3),np.uint8))>0
        if ((f>.5)&edge).sum()/max(1,(f>.5).sum())<.10:return None
        if f.sum()+w.sum()<.35*cv2.resize(mask.astype(np.float32),(37,37)).sum():return None
        return f,w

    def observe(self,frame,region=None,now=None,identify=True):
        now=time.monotonic() if now is None else now
        if self.last_time is not None and now-self.last_time<.35:
            return dict(kind='searching',reason='Waiting for fresh minimap evidence')
        if self.last_time is not None and now-self.last_time>4:
            self.streak=0;self.evidence.clear();self.last_layout=None;self.last_position=None
        self.last_time=now
        if self.frame_size!=frame.size:
            self.frame_size=frame.size;self.streak=0;self.evidence.clear()
        box=self._box(frame,region)
        if box is None or not visible_minimap(frame,box):
            self.streak=0;self.evidence.clear();self.last_layout=None;self.last_position=None
            return dict(kind='missing',reason='Waiting for minimap')
        patch=frame.crop(box)
        if self._outside(patch):
            self.streak=0;self.evidence.clear();self.last_layout=None;self.last_position=None
            return dict(kind='outside',reason='Outdoor minimap detected')
        if not identify:
            return dict(kind='searching',reason='Automatic minimap recognition off')
        template=self._template(patch)
        if template is None:
            self.streak=0;self.evidence.clear();self.last_layout=None;self.last_position=None
            return dict(kind='searching',reason='Waiting for clearer dungeon corridors')
        self._load()
        floor,wall=template
        weight=floor-wall
        known=float(floor.sum()+wall.sum())
        scores=[]
        for layout,reference in self.floors.items():
            correlation=(float(wall.sum())+cv2.matchTemplate(reference,weight,cv2.TM_CCORR))/known
            _,score,_,point=cv2.minMaxLoc(correlation)
            # Reject a second equally good room on the same floor plan too.
            cv2.circle(correlation,point,8,-1,-1)
            _,second,_,_=cv2.minMaxLoc(correlation)
            position=((point[0]+18)/230,(point[1]+18)/230)
            scores.append((score,layout,position,second))
        scores.sort(reverse=True)
        if len(scores)<2:
            self.streak=0
            return dict(kind='searching',reason='More than one layout reference required')
        score,layout,position,second=scores[0]
        margin=score-scores[1][0]
        quality=score>=.80 and score-second>=.025
        for value,key,_,_ in scores:
            self.evidence[key]=self.evidence.get(key,0)*.85+max(-4,(value-score)/.012)
        leaders=sorted(self.evidence,key=self.evidence.get,reverse=True)
        lead=self.evidence[leaders[0]]-self.evidence[leaders[1]]
        consistent=self.last_layout==layout and self.last_position is not None and math.dist(position,self.last_position)<.09
        self.streak=min(5,self.streak+1) if quality and consistent else 1 if quality else 0
        self.last_layout,self.last_position=layout,position
        if self.streak<3 or lead<4 or leaders[0]!=layout or margin<.012:
            return dict(kind='searching',reason='Comparing corridors',score=float(score),margin=float(margin))
        return dict(kind='match',layout=layout,reference_position=position,confidence=float(min(1,score)),
                    margin=float(margin),streak=self.streak,region=list(box),method='temporal-corridors')
