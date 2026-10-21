import tempfile
import unittest
from unittest.mock import patch

from app import App


class DashboardBudgetTests(unittest.TestCase):
    def test_goal_labels_progress_and_keeps_assumptions_short(self):
        with tempfile.TemporaryDirectory() as directory,patch('sanctum_panel.game_is_foreground',return_value=False):
            app=App(directory,hotkeys=False)
            try:
                app.ledger.configure(rank=500,rank_points=0,target=1000)
                app.refresh()
                self.assertEqual(app.goal_progress_text.get(),'Rank 500 / 1,000 · 50.0%')
                self.assertLessEqual(len(app.goal_details_text.get().splitlines()),3)
                self.assertIn('Estimated playtime:',app.playtime_text.get())
            finally:app.close()

    def test_budget_is_readable_and_opens_its_settings_without_changing_the_ledger(self):
        with tempfile.TemporaryDirectory() as directory, patch('sanctum_panel.game_is_foreground', return_value=False):
            app = App(directory, hotkeys=False)
            try:
                app.ledger.configure(daily_tickets=18)
                app.refresh()
                baseline = app.ledger.summary()
                self.assertEqual(app.budget_panel.target.get(), '536,032')
                self.assertEqual(app.budget_panel.parts['keys'].get(), '200,000')
                self.assertEqual(app.budget_panel.parts['gear'].get(), '117,143')
                app.budget_panel.settings_button.invoke()
                self.assertEqual(app.tabs.tab(app.tabs.select(), 'text').strip(), 'Settings')
                self.assertEqual(app.settings_section.get(), 'Goals & budget')
                self.assertEqual(app.ledger.summary(), baseline)
            finally:
                app.close()

    def test_zero_planned_runs_do_not_display_a_misleading_per_run_cash_target(self):
        with tempfile.TemporaryDirectory() as directory, patch('sanctum_panel.game_is_foreground', return_value=False):
            app = App(directory, hotkeys=False)
            try:
                app.ledger.configure(daily_tickets=0, runs_per_play_day=0)
                app.refresh()
                self.assertEqual(app.budget_panel.target.get(), '—')
                self.assertTrue(all(value.get() == '—' for value in app.budget_panel.parts.values()))
                self.assertIn('No planned runs.', app.budget_panel.details.get())
                app.budget_panel.detail_button.invoke()
                self.assertEqual(app.budget_panel.detail_label.winfo_manager(), 'pack')
                app.budget_panel.detail_button.invoke()
                self.assertEqual(app.budget_panel.detail_label.winfo_manager(), '')
            finally:
                app.close()
