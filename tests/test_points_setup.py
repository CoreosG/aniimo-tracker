import tempfile
import unittest
from unittest.mock import patch
from app import App


class PointsSetupTests(unittest.TestCase):
    def test_zero_point_result_saves_and_reopens_without_a_forecast_margin(self):
        with tempfile.TemporaryDirectory() as directory,patch('sanctum_panel.game_is_foreground',return_value=False):
            app=App(directory,hotkeys=False)
            try:
                app.ledger.correct_stats(lifetime_points=10000)
                app.fields['points'].set('0')
                self.assertTrue(app.quick_save_run(),app.status.get())
                self.assertEqual(len(app.ledger.runs()),1)
            finally:app.close()
            reopened=App(directory,hotkeys=False)
            try:
                self.assertEqual(reopened.ledger.summary()['lifetime_points'],10000)
            finally:reopened.close()

    def test_total_only_setup_displays_points_before_emperor_and_eggs_after(self):
        with tempfile.TemporaryDirectory() as directory,patch('sanctum_panel.game_is_foreground',return_value=False):
            app=App(directory,hotkeys=False)
            try:
                app.correct_stats_dialog();editor=app.stats_editor
                editor.fields['lifetime_points'].set('10000');editor.save_button.invoke()
                state=app.ledger.summary()
                self.assertEqual(state['lifetime_points'],10000)
                self.assertFalse(state['is_emperor'])
                self.assertEqual(app.card_values['rank'].get(),'10,000')
                self.assertIn('4,550 points to Egg Emperor',app.progress_caption.get())
                app.correct_stats_dialog();editor=app.stats_editor
                editor.fields['lifetime_points'].set('54837');editor.save_button.invoke()
                self.assertEqual(app.card_values['rank'].get(),'54,837')
                self.assertIn('223 eggs',app.progress_caption.get())
                self.assertIn('147/180',app.progress_caption.get())
                self.assertIn('54,837 / 194,550',app.goal_progress_text.get())
            finally:app.close()

    def test_unknown_total_is_not_presented_as_a_confirmed_emperor_count(self):
        with tempfile.TemporaryDirectory() as directory,patch('sanctum_panel.game_is_foreground',return_value=False):
            app=App(directory,hotkeys=False)
            try:
                self.assertEqual(app.card_values['rank'].get(),'—')
                self.assertNotIn('177',app.progress_caption.get())
                app.fields['points'].set('200');app.fields['lifetime'].set('10000')
                self.assertTrue(app.quick_save_run())
                self.assertEqual(app.ledger.summary()['total_points'],10000)
                self.assertFalse(app.ledger.summary()['is_emperor'])
            finally:app.close()

    def test_optional_egg_calibration_requires_explicit_selection(self):
        with tempfile.TemporaryDirectory() as directory,patch('sanctum_panel.game_is_foreground',return_value=False):
            app=App(directory,hotkeys=False)
            try:
                app.correct_stats_dialog();editor=app.stats_editor
                editor.calibrate.set(True)
                for key,value in dict(lifetime_points='47723',rank='184',rank_points='53').items():editor.fields[key].set(value)
                editor.save_button.invoke()
                self.assertEqual(app.ledger.settings()['lifetime_offset'],14550)
                self.assertEqual(app.ledger.summary()['eggs'],184)
            finally:app.close()
