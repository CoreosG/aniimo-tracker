import tempfile
import unittest
from datetime import timedelta
from unittest.mock import patch

from app import App


class AnalyticsUITests(unittest.TestCase):
    def test_period_results_open_the_existing_editor_and_keep_unknown_loot_last_when_sorted(self):
        with tempfile.TemporaryDirectory() as directory,patch('sanctum_panel.game_is_foreground',return_value=False):
            app=App(directory,hotkeys=False)
            try:
                day=app.ledger.game_day()
                app.ledger.record_run(points=200,money=999999,day=str(day-timedelta(days=5)))
                known=app.ledger.record_run(points=190,money=0)
                unknown=app.ledger.record_run(points=180)
                app.refresh()
                panel=app.analytics
                panel.period.set('Today');panel.refresh()
                self.assertEqual(set(panel.results.get_children()),{str(known),str(unknown)})
                self.assertEqual(len(panel.charts),4)
                self.assertIn('Estimated time: 24 min',panel.range_text.get())
                panel.sort_results('money')
                self.assertEqual(panel.results.get_children(),(str(known),str(unknown)))
                panel.sort_results('money')
                self.assertEqual(panel.results.get_children(),(str(known),str(unknown)))
                panel.results.selection_set(str(known));panel.edit_selected()
                self.assertEqual(app.run_editor.fields['points'].get(),'190')
                self.assertEqual(app.run_editor.fields['money'].get(),'0')
            finally:app.close()
