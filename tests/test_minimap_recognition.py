import unittest
import tempfile
import weakref

from PIL import Image, ImageDraw
from minimap_recognition import MinimapRecognizer
from party_protocol import evidence_score


def floor_plan(alternate=False):
    image=Image.new('RGB',(1024,1024),(25,25,25))
    draw=ImageDraw.Draw(image)
    draw.rectangle((200,200,345,335),fill=(195,190,185))
    draw.rectangle((280,280,315,460),fill=(195,190,185))
    draw.rectangle((310,370,470,405),fill=(195,190,185))
    draw.rectangle((220,220,245,245),fill=(25,25,25))
    if alternate:draw.rectangle((200,200,345,300),fill=(25,25,25))
    return image


def hud(reference,point=(300,300),size=(1280,720)):
    image=Image.new('RGB',size,(40,50,70))
    patch=reference.crop((point[0]-80,point[1]-80,point[0]+80,point[1]+80))
    mask=Image.new('L',(160,160));ImageDraw.Draw(mask).ellipse((0,0,159,159),fill=255)
    image.paste(patch,(25,25),mask)
    draw=ImageDraw.Draw(image)
    draw.ellipse((25,25,185,185),outline=(220,220,220),width=3)
    draw.polygon(((105,96),(113,112),(97,112)),fill=(255,230,30))
    return image


class MinimapRecognitionTests(unittest.TestCase):
    def test_frames_are_released_and_old_packs_do_not_skip_outdoor_checks(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertIsNone(MinimapRecognizer.from_assets(folder,(32,39)))
        reference=floor_plan()
        matcher=MinimapRecognizer({32:reference,39:floor_plan(True)})
        for i in range(50):
            frame=hud(reference,(315,335))
            released=weakref.ref(frame)
            matcher.observe(frame,now=i*.8)
            del frame
            self.assertIsNone(released(),'Recognizer must not retain screen frames')

    def test_confirmed_minimap_evidence_is_shareable_but_lower_than_clear_portals(self):
        reference=floor_plan()
        matcher=MinimapRecognizer({32:reference,39:floor_plan(True)})
        for i in range(3):reading=matcher.observe(hud(reference,(315,335)),now=i*.8)
        self.assertEqual(evidence_score(reading),.8)
        self.assertEqual(evidence_score(reading,39),0,'A reading cannot be reused for another layout')
        portals=dict(map_screen=True,candidates=[39],scores=dict(orange=.95,blue=.94))
        self.assertGreater(evidence_score(portals),evidence_score(reading))
        self.assertEqual(evidence_score({**reading,'streak':1}),0)
        self.assertEqual(evidence_score({**reading,'confidence':float('nan')}),0)

    def test_repeated_rooms_and_grassy_outdoors_never_choose_a_layout(self):
        reference=floor_plan()
        matcher=MinimapRecognizer({32:reference,39:reference.copy()})
        for i in range(10):
            result=matcher.observe(hud(reference,(315,335)),now=i*.8)
            self.assertNotEqual(result['kind'],'match')
        grass=Image.new('RGB',(1024,1024),(65,125,70))
        matcher=MinimapRecognizer({32:reference,39:floor_plan(True)})
        for i in range(8):
            self.assertEqual(matcher.observe(hud(grass),now=i*.8)['kind'],'outside')

    def test_one_screenshot_burst_and_a_missing_hud_cannot_confirm(self):
        reference=floor_plan()
        matcher=MinimapRecognizer({32:reference,39:floor_plan(True)})
        frame=hud(reference,(315,335))
        for now in (0,.01,.02,.03,.04):
            self.assertNotEqual(matcher.observe(frame,now=now)['kind'],'match')
        self.assertEqual(matcher.observe(Image.new('RGB',(1280,720)),now=1)['kind'],'missing')
        self.assertNotEqual(matcher.observe(frame,now=1.8)['kind'],'match')

    def test_scaled_and_manually_positioned_minimap_uses_client_relative_coordinates(self):
        reference=floor_plan()
        for size in ((1280,720),(3840,2160)):
            matcher=MinimapRecognizer({32:reference,39:floor_plan(True)})
            frame=hud(reference,(315,335)).resize(size)
            for i in range(3):result=matcher.observe(frame,now=i*.8)
            self.assertEqual(result['kind'],'match',result)
            self.assertEqual(result['layout'],32)
        matcher=MinimapRecognizer({32:reference,39:floor_plan(True)})
        frame=hud(reference,(315,335))
        for i in range(3):result=matcher.observe(frame,region=[25/1280,25/720,185/1280,185/720],now=i*.8)
        self.assertEqual(result['kind'],'match',result)

    def test_a_capture_gap_requires_new_evidence_instead_of_reusing_old_votes(self):
        reference=floor_plan()
        matcher=MinimapRecognizer({32:reference,39:floor_plan(True)})
        frame=hud(reference,(315,335))
        for now in (0,.8,20):
            self.assertNotEqual(matcher.observe(frame,now=now)['kind'],'match')
        self.assertNotEqual(matcher.observe(frame,now=20.8)['kind'],'match')
        self.assertEqual(matcher.observe(frame,now=21.6)['kind'],'match')

    def test_known_outdoor_stone_paths_cannot_confirm_a_dungeon(self):
        # Deliberately indistinguishable geometry: matching the outdoor reference
        # must beat apparent dungeon evidence, even without green terrain.
        reference=floor_plan()
        matcher=MinimapRecognizer({32:reference,39:floor_plan(True)},outdoor=reference)
        for i in range(8):
            result=matcher.observe(hud(reference,(315,335)),now=i*.8)
            self.assertEqual(result['kind'],'outside',result)

    def test_unique_corridors_confirm_after_three_observations_without_portals(self):
        reference=floor_plan()
        matcher=MinimapRecognizer({32:reference,39:floor_plan(True)})
        frame=hud(reference,(315,335))
        self.assertNotEqual(matcher.observe(frame,now=0)['kind'],'match')
        self.assertNotEqual(matcher.observe(frame,now=.8)['kind'],'match')
        result=matcher.observe(frame,now=1.6)
        self.assertEqual(result['kind'],'match',result)
        self.assertEqual(result['layout'],32)
        for actual,expected in zip(result['reference_position'],(315/1024,335/1024)):
            self.assertAlmostEqual(actual,expected,delta=.015)
