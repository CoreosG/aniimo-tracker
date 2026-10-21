import unittest
from PIL import Image
from tutorial import tutorial_steps,ASSETS


class TutorialTests(unittest.TestCase):
    def test_capture_and_save_instructions_follow_custom_shortcuts_in_both_languages(self):
        keys=dict(capture='F6',save='F7',overlay='F10',map='Tab')
        for portuguese in (False,True):
            steps=tutorial_steps(keys.__getitem__,portuguese)
            self.assertIn('F6',steps[1][1]);self.assertIn('F6',steps[2][1])
            self.assertIn('F7',steps[3][1]);self.assertIn('F10',steps[4][1]);self.assertIn('Tab',steps[4][1])
            self.assertNotIn('Ctrl+Shift+F8',' '.join(step[1] for step in steps))

    def test_only_metadata_free_anonymized_examples_are_used(self):
        steps=tutorial_steps(lambda name:name)
        self.assertEqual([step[2] for step in steps if step[2]],['inventory.png','loot.png','points.png'])
        for _,_,name,focus in steps:
            if not name:continue
            with Image.open(ASSETS/name) as image:
                self.assertGreater(image.width,image.height)
                self.assertFalse(image.info)
            self.assertTrue(all(0<=n<=1 for n in focus))
