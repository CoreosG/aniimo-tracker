import unittest
from update_checker import release_info


class UpdateTests(unittest.TestCase):
    def test_new_release_is_available_but_equal_or_older_release_is_not(self):
        feed=dict(version='0.3.0',download_url='https://github.com/CoreosG/aniimo-tracker/releases/download/v0.3.0/AniimoTracker.exe')
        self.assertTrue(release_info(feed,'0.2.0')['available'])
        self.assertFalse(release_info(feed,'0.3.0')['available'])
        self.assertFalse(release_info(feed,'1.0.0')['available'])

    def test_update_links_must_match_the_release_in_this_repository(self):
        for address in ('http://example.com/app.exe','https://example.com/app.exe',
                        'https://github.com/other/project/releases/download/v0.3.0/AniimoTracker.exe'):
            with self.subTest(address=address),self.assertRaises(ValueError):
                release_info(dict(version='0.3.0',download_url=address),'0.2.0')
