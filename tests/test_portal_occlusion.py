"""Synthetic map scenes use only bundled marker crops, never account screenshots."""
import tempfile
import unittest
from PIL import Image, ImageDraw, ImageFont
from asset_paths import ASSETS
from sanctum import Detector


def entry_map(covered=True, controls=True, fully_covered=False, scale=1., reverse=False,
              portal_visible=True):
    image = Image.new('RGB', (1920, 1080), (62, 72, 91))
    if controls:
        image.paste(Image.open(ASSETS / 'map-zoom-plus.png'), (70, 335))
        image.paste(Image.open(ASSETS / 'map-zoom-minus.png'), (70, 660))
    markers = [('orange-full', (1200 if reverse else 600, 650)), ('blue', (600 if reverse else 1200, 650))]
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype('C:/Windows/Fonts/seguisb.ttf', round(16*scale))
    for kind, (cx, cy) in markers:
        marker = Image.open(ASSETS / (kind + '.png')).convert('RGB')
        marker = marker.resize((round(marker.width*scale), round(marker.height*scale)))
        left, top = cx - marker.width // 2, cy - marker.height // 2
        if portal_visible:
            image.paste(marker, (left, top))
        if covered:
            # Different colored party numbers stack across the door centre.
            for label, dy, color in [('1P', -17, '#ffe36c'), ('2P', -2, '#b6ee71'), ('3P', 13, '#83c8eb')]:
                x1, y1, x2, y2 = (cx-round(11*scale), cy+round((dy-2)*scale),
                                   cx+round(12*scale), cy+round((dy+15)*scale))
                draw.rounded_rectangle((x1, y1, x2, y2), radius=round(5*scale), fill=(69, 75, 82))
                draw.text((cx-round(10*scale), cy+round((dy-3)*scale)), label, font=font, fill=color)
        if fully_covered:
            draw.rectangle((left - 3, top - 3, left + marker.width + 3, top + marker.height + 3), fill=(62, 72, 91))
    return image


def outdoor_map():
    image=entry_map(covered=False,reverse=True)
    ImageDraw.Draw(image).polygon([(700,350),(1050,400),(1000,570),(750,550)],fill=(116,130,90))
    return image


class PortalOcclusionTests(unittest.TestCase):
    def test_outdoor_terrain_with_both_portals_does_not_confirm_a_dungeon(self):
        image=outdoor_map()
        with tempfile.TemporaryDirectory() as directory:
            detector=Detector(directory)
            for size in ((1280,720),(1920,1080),(3840,2160)):
                with self.subTest(size=size):
                    reading=detector.detect(image.resize(size,Image.Resampling.LANCZOS))
                    self.assertEqual(reading['candidates'],[])
                    self.assertTrue(reading['map_screen'])

    def test_default_portals_use_the_same_game_coordinates_at_720p_and_4k(self):
        with tempfile.TemporaryDirectory() as directory:
            detector = Detector(directory)
            for size in ((1280,720), (3840,2160)):
                with self.subTest(size=size):
                    image=entry_map(covered=False).resize(size,Image.Resampling.LANCZOS)
                    reading=detector.detect(image)
                    self.assertEqual(reading['candidates'],[32])
                    self.assertLessEqual(abs(reading['orange'][0]-600*size[0]/1920),4)
                    self.assertLessEqual(abs(reading['blue'][0]-1200*size[0]/1920),4)
                    self.assertLessEqual(abs(reading['blue'][1]-650*size[1]/1080),4)

    def test_stacked_party_numbers_on_both_portals_keep_visible_sides_identifiable(self):
        with tempfile.TemporaryDirectory() as directory:
            reading = Detector(directory).detect(entry_map())
            self.assertEqual(reading['candidates'], [32])
            self.assertLess(abs(reading['orange'][0] - 600), 8)
            self.assertLess(abs(reading['blue'][0] - 1200), 8)
            self.assertEqual(reading['orange'][1], 665)

    def test_visible_fragments_preserve_portal_identity_and_zoom_scales(self):
        with tempfile.TemporaryDirectory() as directory:
            detector = Detector(directory)
            for scale in (.8, 1., 1.2):
                with self.subTest(scale=scale):
                    reading = detector.detect(entry_map(scale=scale, reverse=True))
                    self.assertEqual(reading['candidates'], [40])
                    self.assertLess(abs(reading['orange'][0] - 1200), 8)
                    self.assertLess(abs(reading['blue'][0] - 600), 8)
                    self.assertLessEqual(abs(reading['orange'][1] - (650+round(15*scale))), 2)

    def test_party_badges_cannot_bypass_the_full_map_gate(self):
        with tempfile.TemporaryDirectory() as directory:
            reading = Detector(directory).detect(entry_map(controls=False))
            self.assertEqual(reading['candidates'], [])
            self.assertFalse(reading['map_screen'])

    def test_no_direction_is_guessed_when_badges_leave_no_portal_pixels(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(Detector(directory).detect(entry_map(fully_covered=True))['candidates'], [])

    def test_colored_party_badges_without_doorway_fragments_do_not_confirm(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(Detector(directory).detect(entry_map(portal_visible=False))['candidates'], [])

    def test_two_equally_supported_locations_are_ambiguous(self):
        image = entry_map()
        for cx in (600, 1200):
            image.paste(image.crop((cx-40, 610, cx+40, 690)), (cx-40, 310))
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(Detector(directory).detect(image)['candidates'], [])
