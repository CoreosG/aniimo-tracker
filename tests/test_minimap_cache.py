import unittest
from unittest.mock import patch

import cv2
from PIL import Image, ImageDraw

from map_engine import MapEngine


def minimap_frame(model, left=25, size=(1093, 621)):
    frame = Image.new('RGB', size, (35, 38, 46))
    floor = model.reference.crop((220, 220, 380, 380))
    mask = Image.new('L', (160, 160))
    ImageDraw.Draw(mask).ellipse((2, 2, 158, 158), fill=255)
    frame.paste(floor, (left, 25), mask)
    draw = ImageDraw.Draw(frame)
    draw.ellipse((left, 25, left + 160, 185), outline=(210, 210, 210), width=3)
    draw.polygon([(left + 80, 98), (left + 86, 109), (left + 74, 109)], fill=(255, 230, 20))
    return frame


class MinimapCacheTests(unittest.TestCase):
    def test_stable_hud_reuses_discovered_area_without_repeating_circle_search(self):
        model = MapEngine(37)
        frame = minimap_frame(model)
        with patch('cv2.HoughCircles', wraps=cv2.HoughCircles) as circles:
            first = model.match_minimap(frame)
            self.assertIsNotNone(first)
            second = model.match_minimap(frame, previous=first['player'])
            third = model.match_minimap(frame, previous=first['player'])
            self.assertIsNotNone(second)
            self.assertIsNotNone(third)
            self.assertEqual(circles.call_count, 1)
            for result in (second, third):
                for actual, expected in zip(result['player'], first['player']):
                    self.assertAlmostEqual(actual, expected, delta=1)

    def test_misses_rediscover_moved_hud_and_manual_area_takes_precedence(self):
        model = MapEngine(37)
        first = model.match_minimap(minimap_frame(model))
        self.assertIsNotNone(first)
        moved = minimap_frame(model, left=120)
        manual = [120 / moved.width, 25 / moved.height, 280 / moved.width, 185 / moved.height]
        with patch('cv2.HoughCircles', wraps=cv2.HoughCircles) as circles:
            explicit = model.match_minimap(moved, region=manual, previous=first['player'])
            self.assertIsNotNone(explicit)
            self.assertEqual(explicit['region'], [120, 25, 280, 185])
            self.assertEqual(circles.call_count, 0)
            model.match_minimap(moved, previous=first['player'])
            recovered = model.match_minimap(moved, previous=first['player'])
            self.assertIsNotNone(recovered)
            self.assertGreater(circles.call_count, 0)
            self.assertIsNone(model.match_minimap(moved, region=manual, previous=[95, 95]))

    def test_resolution_change_rediscovers_the_hud_immediately(self):
        model = MapEngine(37)
        self.assertIsNotNone(model.match_minimap(minimap_frame(model)))
        with patch('cv2.HoughCircles', wraps=cv2.HoughCircles) as circles:
            self.assertIsNotNone(model.match_minimap(minimap_frame(model, size=(1280, 720))))
            self.assertEqual(circles.call_count, 1)
