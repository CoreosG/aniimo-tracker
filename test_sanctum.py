import unittest
import tempfile
from pathlib import Path
from PIL import Image, ImageDraw
from sanctum import candidates_from_portals, WatchSession, Detector


class SanctumTests(unittest.TestCase):
    def test_monochrome_custom_markers_remain_recognizable(self):
        with tempfile.TemporaryDirectory() as folder:
            image = Image.new('RGB', (800,600), (35,38,46))
            draw = ImageDraw.Draw(image)
            draw.ellipse((190,290,210,310), outline=(210,210,210), width=4)
            draw.line((200,288,200,312), fill='white', width=2)
            draw.rectangle((490,290,510,310), outline=(170,170,170), width=4)
            draw.line((488,300,512,300), fill='white', width=2)
            detector = Detector(folder)
            detector.calibrate(image, (200,300), (500,300))
            reading = detector.detect(image)
            self.assertEqual(reading['candidates'], [32])
            self.assertEqual((reading['orange'], reading['blue']), ([200,300], [500,300]))

    def test_portal_icons_without_full_map_interface_do_not_confirm(self):
        import sanctum
        assets=Path(sanctum.__file__).with_name('assets')
        screen=Image.new('RGB',(1920,1080),(45,54,65))
        screen.paste(Image.open(assets/'orange.png'),(1000,300))
        screen.paste(Image.open(assets/'blue.png'),(1124,650))
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(Detector(folder).detect(screen)['candidates'],[],
                             'Portal-like HUD icons alone must not confirm a full map')

    def test_map_only_session_needs_no_run_and_confirmation_is_scoped(self):
        session=WatchSession()
        session.begin(None,standalone=True)
        self.assertTrue(session.watching)
        self.assertIsNone(session.run_id)
        self.assertFalse(session.can_track_minimap)
        session.confirm_map()
        self.assertTrue(session.can_track_minimap)
        session.end();self.assertFalse(session.watching)
        session.resume();self.assertTrue(session.watching)
        session.begin(17)
        self.assertFalse(session.standalone)
        self.assertFalse(session.map_confirmed)
        session.begin(None)
        self.assertFalse(session.watching)

    def test_full_map_confirmation_is_required_per_run_and_survives_pause(self):
        session=WatchSession();session.begin(1)
        self.assertFalse(session.can_track_minimap)
        session.map_key_pressed()
        self.assertFalse(session.can_track_minimap,'A key press alone is not map evidence')
        session.confirm_map()
        self.assertTrue(session.can_track_minimap)
        session.end();self.assertFalse(session.can_track_minimap)
        session.resume();self.assertTrue(session.can_track_minimap)
        session.begin(2);self.assertFalse(session.can_track_minimap)

    def test_resume_same_run_and_pixels_override_a_missed_map_key(self):
        session=WatchSession();session.begin(3)
        session.map_key_pressed()
        self.assertTrue(session.map_open)
        session.observe_screen('minimap')
        self.assertFalse(session.map_open,'Actual gameplay must clear a stuck M state')
        session.end()
        self.assertTrue(session.resume())
        self.assertEqual(session.run_id,3)
        self.assertTrue(session.watching)
        session.observe_screen('full_map')
        self.assertTrue(session.map_open)

    def test_west_portals_do_not_guess_between_two_layouts(self):
        self.assertEqual(candidates_from_portals((500,500),(200,500)), (36,40))
        self.assertEqual(candidates_from_portals((200,500),(500,500)), (32,))
        self.assertEqual(candidates_from_portals((500,500),(500,200)), (39,))
        self.assertEqual(candidates_from_portals((200,500),(500,200)), (35,))

    def test_watcher_only_runs_between_start_and_end_with_toggle(self):
        session = WatchSession()
        self.assertFalse(session.watching)
        session.begin(1)
        self.assertTrue(session.watching)
        session.end()
        session.begin(1)
        self.assertFalse(session.watching)
        session.begin(2)
        self.assertTrue(session.watching)
        session.enable(False)
        self.assertFalse(session.watching)
        session.begin(None)
        session.enable(True)
        self.assertFalse(session.watching)

    def test_local_marker_calibration_finds_portals_after_map_moves(self):
        with tempfile.TemporaryDirectory() as folder:
            image = Image.new('RGB',(800,600),(35,38,46))
            draw = ImageDraw.Draw(image)
            draw.ellipse((190,290,210,310),outline='orange',width=4)
            draw.line((200,288,200,312),fill='white',width=2)
            draw.rectangle((490,290,510,310),outline='cyan',width=4)
            draw.line((488,300,512,300),fill='white',width=2)
            detector = Detector(folder)
            detector.calibrate(image, (200,300), (500,300))
            moved = Image.new('RGB',(900,650),(35,38,46))
            moved.paste(image,(40,20))
            reading = detector.detect(moved)
            self.assertEqual(reading['candidates'], [32])
            self.assertEqual(reading['orange'], [240,320])
            self.assertEqual(reading['blue'], [540,320])

    def test_learned_west_layout_does_not_turn_into_a_direction_guess(self):
        with tempfile.TemporaryDirectory() as folder:
            image = Image.new('RGB',(800,600),(35,38,46))
            draw = ImageDraw.Draw(image)
            draw.ellipse((490,290,510,310),outline='orange',width=4)
            draw.line((500,288,500,312),fill='white',width=2)
            draw.rectangle((190,290,210,310),outline='cyan',width=4)
            draw.line((188,300,212,300),fill='white',width=2)
            draw.rectangle((300,170,450,260),outline='white',width=4)
            detector = Detector(folder)
            detector.calibrate(image,(500,300),(200,300),layout=36)
            self.assertEqual(detector.detect(image)['candidates'],[36])
            blank = Image.new('RGB',(800,600),(35,38,46))
            self.assertEqual(detector.detect(blank)['candidates'],[])


if __name__ == '__main__':
    unittest.main()
