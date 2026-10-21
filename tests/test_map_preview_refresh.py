import tempfile
import unittest
from unittest.mock import patch

from app import App


class MapPreviewRefreshTests(unittest.TestCase):
    def test_map_preview_catches_up_to_the_latest_accepted_position_when_returning_to_map(self):
        with tempfile.TemporaryDirectory() as directory,patch('sanctum_panel.game_is_foreground',return_value=False),patch('sanctum_panel.app_is_foreground',return_value=False):
            app=App(directory,hotkeys=False)
            try:
                panel=app.sanctum
                panel.watch_action()
                panel.accept_layout(39,dict(candidates=[39],orange=[100,500],blue=[100,100]))
                app.tabs.select(app.sanctum_tab);app.update_idletasks()
                panel.paint()
                before=panel.photo
                before_pixels=app.tk.call(str(before),'data','-format','png')
                app.tabs.select(0)
                baseline=app.ledger.summary()
                for point in ([35,35],[60,60]):
                    panel.messages.put((panel.generation,None,dict(minimap=True,match=dict(player=point,inliers=15)),None))
                    panel.tick()
                self.assertIs(panel.photo,before,'Background results should not redraw the hidden map preview')
                self.assertEqual(panel.player,[60,60])

                app.tabs.select(app.sanctum_tab);app.update_idletasks()
                with patch('sanctum_panel.app_is_foreground',return_value=True):
                    panel.tick()
                self.assertIsNot(panel.photo,before)
                after=panel.photo
                self.assertNotEqual(app.tk.call(str(after),'data','-format','png'),before_pixels)
                with patch('sanctum_panel.app_is_foreground',return_value=True):
                    panel.tick()
                self.assertIs(panel.photo,after,'An unchanged accepted position should not repaint every tick')
                self.assertEqual(app.ledger.summary(),baseline)
            finally:app.close()
