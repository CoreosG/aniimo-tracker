import tempfile
import unittest
from unittest.mock import patch
from app import App


class BalanceHistoryTests(unittest.TestCase):
    def test_user_can_edit_a_historical_balance_and_see_large_numbers_before_saving(self):
        with tempfile.TemporaryDirectory() as directory,patch('sanctum_panel.game_is_foreground',return_value=False):
            app=App(directory,hotkeys=False)
            try:
                old=app.ledger.correct_stats(coins=76540000)
                app.ledger.correct_stats(coins=10500000)
                app.refresh();baseline=app.ledger.summary()
                app.show_balance_history();history=app.balance_history
                history.tree.selection_set(str(old));history.edit_button.invoke()
                history.editor.amount.set('7.654M');app.update()
                self.assertIn('7,654,000',history.editor.preview.get())
                history.editor.save_button.invoke();app.update()
                self.assertEqual(next(r['coins'] for r in app.ledger.corrections() if r['id']==old),7654000)
                self.assertEqual(app.ledger.summary(),baseline)
                app.correct_stats_dialog();app.stats_editor.fields['coins'].set('76540000')
                self.assertIn('76,540,000',app.stats_editor.balance_preview.get())
                app.stats_editor.fields['coins'].set('7654000')
                self.assertIn('7,654,000',app.stats_editor.balance_preview.get())
            finally:app.close()

    def test_warning_preference_survives_restart_without_requiring_a_username_edit(self):
        with tempfile.TemporaryDirectory() as directory,patch('sanctum_panel.game_is_foreground',return_value=False):
            app=App(directory,hotkeys=False)
            app.party.name.set('')
            app.party.warn_unfinished.set(False);app.party.save_warning_preference();app.close()
            app=App(directory,hotkeys=False)
            try:self.assertFalse(app.party.warn_unfinished.get())
            finally:app.close()
