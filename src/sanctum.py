from asset_paths import ASSETS
"""Local screen-image recognition and run-scoped map watching.

No game-memory access. Default templates come from the player's captured map;
custom calibration can override them. Map planning uses the local simulator.
"""
import json
import math
from pathlib import Path
from map_catalog import ALL_LAYOUTS,layouts_for

LAYOUTS = (32,34,35,36,37,39,40)
DIRECTIONS = {'E':(32,), 'S':(34,), 'NE':(35,), 'W':(36,40), 'SE':(37,), 'N':(39,)}
SITE_URL = 'https://aniimotools.dev/map/lost-sanctum/'


def candidates_from_portals(orange, blue):
    dx, dy = blue[0]-orange[0], blue[1]-orange[1]
    if math.hypot(dx,dy) < 20:
        return ()
    index = round(math.atan2(-dy,dx) / (math.pi/4)) % 8
    return DIRECTIONS.get(('E','NE','N','NW','W','SW','S','SE')[index], ())


class WatchSession:
    def __init__(self, enabled=True):
        self.enabled, self.run_id, self.paused = enabled, None, False
        self.map_open=False
        self.map_confirmed=False
        self.standalone=False

    @property
    def context_id(self):
        return self.run_id if self.run_id is not None else 'map-only' if self.standalone else None

    @property
    def watching(self):
        return bool(self.enabled and self.context_id is not None and not self.paused)

    def begin(self, run_id,standalone=False):
        standalone=bool(standalone and run_id is None)
        if self.run_id != run_id or self.standalone!=standalone:
            self.run_id, self.paused = run_id, False
            self.standalone=standalone
            self.map_open=False
            self.map_confirmed=False

    @property
    def can_track_minimap(self):
        return self.watching and self.map_confirmed

    def confirm_map(self):
        if self.context_id is not None:self.map_confirmed=True

    def end(self):
        self.paused = True

    def resume(self):
        self.enabled,self.paused,self.map_open=True,False,False
        return self.watching

    def map_key_pressed(self):
        self.map_open=not self.map_open

    def observe_screen(self,kind):
        if kind in ('full_map','minimap'):
            self.map_open=kind=='full_map'

    def enable(self, value):
        self.enabled = bool(value)
        if value:
            self.paused = False


class Detector:
    def __init__(self, folder,difficulty='Chaos'):
        self.folder = Path(folder)
        self.difficulty=difficulty
        self.folder.mkdir(parents=True, exist_ok=True)

    @property
    def calibrated(self):
        return all(self.template_path(kind).exists() for kind in ('orange','blue'))

    def template_path(self, kind):
        custom = self.folder / f'{kind}.png'
        return custom if custom.exists() else ASSETS / f'{kind}.png'

    def is_map_screen(self,image):
        """Require the full-map zoom controls, independent of portal-like HUD icons."""
        import cv2
        import numpy as np
        from PIL import Image
        # HUD scales with resolution; map zoom only changes the floor plan.
        normalized=image.convert('RGB').resize((round(image.width*1080/image.height),1080))
        frame=np.asarray(normalized)
        positions=[]
        for name,top,bottom in (('plus',280,410),('minus',605,740)):
            with Image.open(ASSETS/f'map-zoom-{name}.png') as im:
                template=np.asarray(im.convert('RGB'))
            crop=frame[top:bottom,round(frame.shape[1]*.02):round(frame.shape[1]*.09)]
            if crop.shape[1]<template.shape[1]:return False
            _,score,_,point=cv2.minMaxLoc(cv2.matchTemplate(crop,template,cv2.TM_CCOEFF_NORMED))
            if score<.88:return False
            positions.append(point[0])
        return abs(positions[0]-positions[1])<8

    def calibrate(self, image, orange, blue, player=None, layout=None):
        import numpy as np
        import cv2
        from PIL import Image
        image = image.convert('RGB')
        for kind, point in [('orange',orange),('blue',blue),('player',player)]:
            if point is not None:
                x,y = map(int,point)
                radius = 13 if kind != 'player' else 10
                if x-radius < 0 or y-radius < 0 or x+radius >= image.width or y+radius >= image.height:
                    raise ValueError('Select the center of each marker, away from the image edge.')
                patch = image.crop((x-radius,y-radius,x+radius+1,y+radius+1))
                if np.asarray(patch).std() < 5:
                    raise ValueError('That patch has too little detail; click the visible marker itself.')
                patch.save(self.folder / f'{kind}.png')
        if layout in ALL_LAYOUTS:
            signature = self._signature(np.asarray(image),orange,blue)
            cv2.imwrite(str(self.folder / f'layout-{layout}.png'),signature)

    @staticmethod
    def _signature(image, orange, blue):
        import numpy as np
        import cv2
        a,b = np.array(orange,dtype=float),np.array(blue,dtype=float)
        d = b-a
        length2 = float(d @ d)
        if length2 < 400:
            raise ValueError('The two portals are too close to distinguish.')
        scale = 180 / length2
        c,s = d[0]*scale,d[1]*scale
        matrix = np.array([[c,s,350-c*a[0]-s*a[1]],[-s,c,250+s*a[0]-c*a[1]]],dtype=np.float32)
        gray = cv2.cvtColor(image,cv2.COLOR_RGB2GRAY)
        result = cv2.warpAffine(gray,matrix,(700,500))
        return cv2.GaussianBlur(cv2.Canny(result,45,100),(5,5),0)

    def _partly_visible_portal(self,frame,kind):
        """Recover one covered icon from its visible shape and absolute colors.

        Only used after the full-map UI has been confirmed.
        Search colored components locally, normally using at least half of the
        template. A distinctive blue rim can use a smaller fragment with a
        stricter ambiguity margin. Never lower the whole-icon threshold.
        """
        import cv2
        import numpy as np
        from PIL import Image
        hsv=cv2.cvtColor(frame,cv2.COLOR_RGB2HSV)
        lo,hi=((8,95,110),(35,255,255)) if kind=='orange' else ((90,65,120),(135,255,255))
        colored=cv2.inRange(hsv,np.array(lo),np.array(hi))
        count,_,stats,_=cv2.connectedComponentsWithStats(colored)
        boxes=[(x,y,w,h) for x,y,w,h,area in stats[1:] if 4<=area<=2500 and w<100 and h<100]
        with Image.open(self.template_path(kind)) as im:template=np.asarray(im.convert('RGB'))
        proposals=[]
        for factor in (.8,1.,1.2):
            size=tuple(max(9,round(n*factor)) for n in template.shape[1::-1])
            patch=cv2.resize(template,size)
            w,h=size
            for x,y,bw,bh in boxes:
                left,top=max(0,x-w),max(0,y-h)
                crop=frame[top:min(frame.shape[0],y+bh+h),left:min(frame.shape[1],x+bw+w)]
                if crop.shape[0]<h or crop.shape[1]<w:continue
                masks=[]
                for horizontal,vertical in ((0,0),(0,1),(1,0),(1,1)):
                    mask=np.ones((h,w),np.uint8)
                    # Include a small gutter because player badges have soft edges.
                    ys=slice(0,h//2+2) if vertical==0 else slice(h//2-2,h)
                    xs=slice(0,w//2+2) if horizontal==0 else slice(w//2-2,w)
                    mask[ys,xs]=0
                    masks.append((mask,.92,32,.025))
                for axis in (0,1):
                    for side in (0,1):
                        mask=np.ones((h,w),np.uint8)
                        cut=(h if axis==0 else w)//2
                        part=slice(0,cut) if side==0 else slice(cut,None)
                        if axis==0:mask[part,:]=0
                        else:mask[:,part]=0
                        # Larger visible fragments carry more shape evidence.
                        substantial=mask.sum()>=400
                        masks.append((mask,.92 if substantial else .95,32 if substantial else 24,.025))
                if kind=='blue':
                    for side in (0,1):
                        mask=np.zeros((h,w),np.uint8)
                        band=max(1,h//5)
                        if side==0:mask[:band,:]=1
                        else:mask[-band:,:]=1
                        if mask.sum()>=200:masks.append((mask,.93,24,.04))
                for mask,threshold,max_error,margin in masks:
                    response=cv2.matchTemplate(crop,patch,cv2.TM_CCOEFF_NORMED,mask=mask)
                    response[~np.isfinite(response)]=-1
                    _,score,_,point=cv2.minMaxLoc(response)
                    if score<threshold:continue
                    px,py=point
                    observed=crop[py:py+h,px:px+w]
                    error=float(np.sqrt(np.mean((observed.astype(float)-patch)[mask.astype(bool)]**2)))
                    if error>max_error:continue
                    proposals.append((score,[left+px+w//2,top+py+h//2],margin))
        proposals.sort(reverse=True)
        if not proposals:return None
        score,point,margin=proposals[0]
        alternative=max((s for s,p,m in proposals if math.dist(p,point)>25),default=-1)
        if score-alternative<margin:return None
        return [int(n) for n in point],round(score,3)

    @staticmethod
    def _marker_regions(frame, template, kind, pad=None):
        """Find small color-supported search areas; template scores still decide."""
        import cv2
        import numpy as np
        bounds = {'orange': ((8,95,110),(35,255,255)),
                  'blue': ((90,65,120),(135,255,255)),
                  'player': ((18,100,180),(38,255,255))}
        lo,hi = (np.array(value) for value in bounds[kind])
        # A custom monochrome calibration has no usable color hint. Preserve
        # its original full-image matching behavior rather than rejecting it.
        if cv2.countNonZero(cv2.inRange(cv2.cvtColor(template,cv2.COLOR_RGB2HSV),lo,hi)) < 4:
            return [(0,0,frame.shape[1],frame.shape[0])]
        mask = cv2.inRange(cv2.cvtColor(frame,cv2.COLOR_RGB2HSV),lo,hi)
        _,_,stats,_ = cv2.connectedComponentsWithStats(mask)
        pad = max(template.shape[:2])*2 if pad is None else pad
        regions = []
        for x,y,w,h,area in stats[1:]:
            if not 4 <= area <= 5000 or w > 140 or h > 140:
                continue
            rect = tuple(int(value) for value in (max(0,x-pad),max(0,y-pad),min(frame.shape[1],x+w+pad),min(frame.shape[0],y+h+pad)))
            # Color fragments from one icon share one search; do not match the
            # same doorway separately for every disconnected colored stroke.
            index = 0
            while index < len(regions):
                other = regions[index]
                if rect[0] <= other[2] and other[0] <= rect[2] and rect[1] <= other[3] and other[1] <= rect[3]:
                    regions.pop(index)
                    rect = (min(rect[0],other[0]),min(rect[1],other[1]),max(rect[2],other[2]),max(rect[3],other[3]))
                    index = 0
                else:
                    index += 1
            regions.append(rect)
        return regions

    def _fragmented_portal(self, frame, kind):
        """Match separated visible rim/door fragments around stacked badges.

        A clean fragment proposes a location, then the combined visible white
        doorway and the correct portal color must support it. Badge colors alone
        cannot confirm a door. Used only after the full-map gate, with default
        templates; custom calibration retains its previous matching behavior.
        """
        import cv2
        import numpy as np
        from PIL import Image
        path = ASSETS/'orange-full.png' if kind == 'orange' else self.template_path(kind)
        if not path.exists():
            return None
        with Image.open(path) as image:
            template = np.asarray(image.convert('RGB'))
        regions = self._marker_regions(frame, template, kind, pad=max(template.shape[:2]))
        proposals = []
        for factor in (.8, 1., 1.2):
            width, height = (max(9, round(size*factor)) for size in template.shape[1::-1])
            patch = cv2.resize(template, (width, height))
            gray_patch = cv2.cvtColor(patch, cv2.COLOR_RGB2GRAY)
            hsv = cv2.cvtColor(patch, cv2.COLOR_RGB2HSV)
            lo, hi = ((8, 95, 110), (35, 255, 255)) if kind == 'orange' else ((90, 65, 120), (135, 255, 255))
            colored = cv2.inRange(hsv, np.array(lo), np.array(hi)).astype(bool)
            white = (patch.min(axis=2) > 195) & (np.ptp(patch, axis=2) < 65)
            foreground = colored | white
            masks = []
            # Opposite sides remain visible when all three badges cover the
            # middle. Top/bottom fragments handle a badge over one half.
            for fraction in (.15, .25, .33):
                sides = np.zeros((height, width), np.uint8)
                band = max(2, round(width*fraction))
                sides[:, :band] = 1
                sides[:, -band:] = 1
                masks.append(sides)
                if fraction != .33:
                    for right_side in (False, True):
                        side = np.zeros((height, width), np.uint8)
                        if right_side:
                            side[:, -band:] = 1
                        else:
                            side[:, :band] = 1
                        masks.append(side)
            for fraction in (.25, .33):
                band = max(2, round(height*fraction))
                for bottom in (False, True):
                    mask = np.zeros((height, width), np.uint8)
                    mask[-band:] = 1 if bottom else 0
                    if not bottom:
                        mask[:band] = 1
                    masks.append(mask)
            for left, top, right, bottom in regions:
                crop = frame[top:bottom, left:right]
                if crop.shape[0] < height or crop.shape[1] < width:
                    continue
                gray_crop = cv2.cvtColor(crop, cv2.COLOR_RGB2GRAY)
                for region_mask in masks:
                    mask = (region_mask.astype(bool) & foreground).astype(np.uint8)
                    if mask.sum() < 45 or colored[mask.astype(bool)].sum() < 5:
                        continue
                    response = cv2.matchTemplate(gray_crop, gray_patch, cv2.TM_CCOEFF_NORMED, mask=mask)
                    response[~np.isfinite(response)] = -1
                    _, score, _, point = cv2.minMaxLoc(response)
                    if score < .90:
                        continue
                    px, py = point
                    observed = crop[py:py+height, px:px+width]
                    error = np.sqrt(np.mean((observed.astype(float)-patch)**2, axis=2))
                    visible = (error < 38) & foreground
                    # Require genuine doorway shape plus its color, across
                    # spatially separated fragments, rather than a player number.
                    if visible.sum() < max(75, foreground.sum()*.30):
                        continue
                    if (visible & colored).sum() < max(8, colored.sum()*.15):
                        continue
                    if (visible & white).sum() < max(18, white.sum()*.25):
                        continue
                    ys, xs = np.nonzero(visible)
                    if np.ptp(xs) < width*.55 or np.ptp(ys) < height*.35:
                        continue
                    rms = float(np.sqrt(np.mean(error[mask.astype(bool)]**2)))
                    if rms > 32:
                        continue
                    # Covered pixels lower shared evidence relative to a clean
                    # whole icon, even when the remaining rim matches perfectly.
                    coverage = min(1., visible.sum()/max(1, foreground.sum()))
                    confidence = min(.94, float(score))*(.75+.25*coverage)
                    # The original orange calibration is its bottom fragment,
                    # 15 pixels below this full crop's centre. Keep that anchor
                    # so map registration does not jump when recovery is used.
                    anchor_y = height//2 + (round(15*factor) if kind == 'orange' else 0)
                    proposals.append((confidence, [left+px+width//2, top+py+anchor_y]))
        proposals.sort(reverse=True)
        if not proposals:
            return None
        score, point = proposals[0]
        alternative = max((value for value, other in proposals if math.dist(point, other)>25), default=-1)
        if score-alternative < .035:
            return None
        return point, round(float(score), 3)

    def detect(self, image):
        if not (ASSETS/'simulator'/f'layout-{layouts_for(self.difficulty)[0]}.json').exists():
            return dict(candidates=[],reason='Download the map pack in Map & routes first.')
        import numpy as np
        import cv2
        from PIL import Image
        cv2.setNumThreads(2)
        if not self.calibrated:
            return dict(candidates=[], reason='Calibrate orange/blue portal markers once using an M-map screenshot.')
        # Default HUD marker crops were captured at 1080p. Normalize the whole
        # game client once so 720p/4K use the same evidence thresholds; return
        # positions in the caller's original pixel space for calibration and map
        # registration. Custom captures remain tied to their calibration size.
        custom=any((self.folder/f'{kind}.png').exists() for kind in ('orange','blue','player'))
        if not custom and image.height!=1080:
            normalized=image.resize((max(1,round(image.width*1080/image.height)),1080),Image.Resampling.LANCZOS)
            reading=self.detect(normalized)
            for kind in ('orange','blue','player'):
                if kind in reading:
                    point=reading[kind]
                    reading[kind]=[round(point[0]*image.width/normalized.width),round(point[1]*image.height/normalized.height)]
            return reading
        if not (self.folder/'orange.png').exists() and not self.is_map_screen(image):
            return dict(candidates=[],map_screen=False,reason='Full map is not open; waiting for the game map.')
        frame = np.asarray(image.convert('RGB'))
        result = {}
        scores = {}
        for kind in ('orange','blue','player'):
            path = self.template_path(kind)
            if not path.exists():
                continue
            with Image.open(path) as im:
                template = np.asarray(im.convert('RGB'))
            regions = self._marker_regions(frame,template,kind)
            best = (-1,None)
            angles = (0,45,90,135,180,225,270,315) if kind == 'player' else (0,)
            for factor in (.8,1.,1.2):
                size = (max(9,round(template.shape[1]*factor)), max(9,round(template.shape[0]*factor)))
                if size[0] > frame.shape[1] or size[1] > frame.shape[0]:
                    continue
                patch = cv2.resize(template,size)
                for angle in angles:
                    rotated = patch
                    if angle:
                        matrix = cv2.getRotationMatrix2D((size[0]/2,size[1]/2),angle,1)
                        rotated = cv2.warpAffine(patch,matrix,size,borderMode=cv2.BORDER_REFLECT)
                    for left,top,right,bottom in regions:
                        crop=frame[top:bottom,left:right]
                        if crop.shape[0] < size[1] or crop.shape[1] < size[0]:
                            continue
                        response = cv2.matchTemplate(crop,rotated,cv2.TM_CCOEFF_NORMED)
                        _,score,_,point = cv2.minMaxLoc(response)
                        if score > best[0]:
                            best = (score,[left+point[0]+size[0]//2,top+point[1]+size[1]//2])
            if best[0] >= (.86 if kind == 'player' else .83):
                result[kind],scores[kind] = best[1],round(best[0],3)
        occluded=[]
        missing=[kind for kind in ('orange','blue') if kind not in result]
        if missing and not (self.folder/'orange.png').exists():
            for kind in missing:
                recovered=self._fragmented_portal(frame,kind)
                if not recovered:
                    recovered=self._partly_visible_portal(frame,kind)
                if recovered:
                    result[kind],scores[kind]=recovered
                    occluded.append(kind)
        if 'orange' not in result or 'blue' not in result:
            return dict(**result,scores=scores,candidates=[],map_screen=True, reason='Entrance hidden or unclear · waiting for both portals. Player markers can cover a door; move away briefly or fit both doors on the map.')
        if all(result[k][0] < image.width*.3 and result[k][1] < image.height*.35 for k in ('orange','blue')):
            return dict(candidates=[],map_screen=True,reason='Only corner minimap markers are visible; open the full M map.')
        candidates = list(candidates_from_portals(result['orange'],result['blue']))
        # The map-36 pair is diagonally southwest; map 40 is horizontal west.
        # Compare actual portal vectors rather than rounding both into one octant.
        if not (self.folder/'orange.png').exists() or self.difficulty in ('Beginner','Hard'):
            data=json.loads((ASSETS/'maps.json').read_text())
            dx,dy=result['blue'][0]-result['orange'][0],result['blue'][1]-result['orange'][1]
            observed=math.atan2(dy,dx)
            ranked=[]
            for candidate in layouts_for(self.difficulty):
                if str(candidate) in data:
                    a,b=data[str(candidate)]['orange'],data[str(candidate)]['blue']
                else:
                    entry=json.loads((ASSETS/'simulator'/f'layout-{candidate}.json').read_text())
                    a,b=([entry['doors'][door]['x']*entry['img']['w'],entry['doors'][door]['y']*entry['img']['h']] for door in ('main','side'))
                angle=math.atan2(b[1]-a[1],b[0]-a[0])
                error=abs(math.atan2(math.sin(observed-angle),math.cos(observed-angle)))
                ranked.append((error,candidate))
            ranked.sort()
            if ranked[0][0]<math.radians(10) and ranked[1][0]-ranked[0][0]>math.radians(8):
                candidates=[ranked[0][1]]
            else:candidates=[candidate for error,candidate in ranked if error<math.radians(10)]
        if len(candidates) > 1:
            signature = self._signature(frame,result['orange'],result['blue']).astype(float)
            matches = []
            for candidate in candidates:
                path = self.folder / f'layout-{candidate}.png'
                if path.exists():
                    reference = cv2.imread(str(path),cv2.IMREAD_GRAYSCALE).astype(float)
                    score = float((signature*reference).sum()) / max(1.,float(np.linalg.norm(signature)*np.linalg.norm(reference)))
                    matches.append((score,candidate))
            matches.sort(reverse=True)
            if matches and matches[0][0] > .72 and (len(matches)==1 or matches[0][0]-matches[1][0] > .1):
                candidates = [matches[0][1]]
        return dict(**result,candidates=candidates,scores=scores,map_screen=True,occluded_portals=occluded,
                    reason='Confirmed by portal direction' if len(candidates)==1 else 'Portal direction is shared; choose the matching layout.')
