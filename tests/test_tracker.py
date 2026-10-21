import tempfile
import unittest
from datetime import date
from pathlib import Path

from tracker_core import ticket_cost, Ledger, forecast, break_even, DEFAULTS


class BudgetTests(unittest.TestCase):
    def test_eighteen_daily_solo_runs_include_weekly_discount_and_all_costs(self):
        result=break_even({**DEFAULTS,'daily_tickets':18})
        self.assertEqual(result['weekly_runs'],126)
        self.assertEqual(result['weekly_gear'],14760000)
        self.assertEqual(result['daily_tickets_cost'],3940000)
        self.assertAlmostEqual(result['per_run'],536031.746031746)

    def test_party_uses_one_key_and_skip_days_change_weekly_gear_discounts(self):
        result=break_even({**DEFAULTS,'daily_tickets':18,'party_keys':1,'budget_party':True,'play_days_week':3})
        self.assertEqual(result['weekly_runs'],54)
        self.assertEqual(result['weekly_gear'],6120000)
        # Tickets are bought all seven days, while runs occur only three days.
        self.assertAlmostEqual(result['tickets_per_run'],27580000/54)
        self.assertEqual(result['keys_per_run'],100000)


class TrackerTests(unittest.TestCase):
    def test_failed_run_upgrade_preserves_old_results_and_correction_boundaries(self):
        import sqlite3
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'old.db'
            db = sqlite3.connect(path)
            try:
                db.execute('''CREATE TABLE runs(id INTEGER PRIMARY KEY,timestamp TEXT,day TEXT,points INTEGER,
                    money INTEGER,expenses INTEGER,bonus INTEGER,money_image TEXT,points_image TEXT,
                    notes TEXT,consumes_ticket INTEGER,applied INTEGER NOT NULL DEFAULT 1,start_id INTEGER,source_key TEXT)''')
                db.execute("INSERT INTO runs VALUES(1,'2026-10-19','2026-10-19',200,300000,0,0,'loot.png','points.png','Old result',1,1,NULL,'old-result')")
                db.commit()
            finally:
                db.close()
            ledger = Ledger(path)
            row = ledger.runs()[0]
            self.assertEqual((row['failed'], row['points'], row['money_image'], row['notes']),
                             (0, 200, 'loot.png', 'Old result'))
            ledger.correct_stats(rank=184, rank_points=53, tickets=99, coins=900000)
            ledger.update_run(1, points=-140)
            self.assertEqual((ledger.summary()['rank'], ledger.summary()['rank_points'],
                              ledger.summary()['tickets'], ledger.summary()['coins']),
                             (184, 53, 99, 900000))
            ledger.record_run(points=-140)
            self.assertEqual((ledger.summary()['rank'], ledger.summary()['rank_points'],
                              ledger.summary()['tickets']), (183, 93, 98))

    def test_failed_outcomes_can_be_corrected_without_replacing_a_run(self):
        with tempfile.TemporaryDirectory() as folder:
            ledger = Ledger(Path(folder) / 'runs.db')
            run = ledger.record_run(points=200, money=0)
            ledger.update_run(run, points=-140)
            self.assertEqual((ledger.runs()[0]['id'], ledger.runs()[0]['failed'],
                              ledger.summary()['rank'], ledger.summary()['rank_points'],
                              ledger.summary()['tickets']), (run, 1, 176, 40, 104))
            ledger.update_run(run, points=200)
            self.assertEqual(ledger.runs()[0]['failed'], 0)
            ledger.update_run(run, points=0, failed=True)
            self.assertEqual(ledger.runs()[0]['failed'], 1)
            zero = ledger.record_run(points=0, failed=True)
            self.assertEqual(ledger.runs()[0]['id'], zero)
            self.assertEqual(ledger.runs()[0]['failed'], 1)
            with self.assertRaises(ValueError): ledger.update_run(zero, points=100, failed=True)
            with self.assertRaises(ValueError): ledger.record_run(points=100, failed=True)

    def test_failed_run_deducts_points_and_ticket_without_training_successful_pace(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'runs.db'
            ledger = Ledger(path)
            ledger.configure(rank=184, rank_points=53, target=190, normal_points=180, first_points=180)
            start = ledger.start_run(900000)
            ledger.record_run(points=-140, start_id=start)
            restored = Ledger(path)
            state = restored.summary()
            self.assertEqual((state['rank'], state['rank_points'], state['tickets'], state['coins']),
                             (183, 93, 104, 900000))
            self.assertIsNone(restored.active_start())
            self.assertEqual((restored.summary()['normal'], forecast(restored)['play_minutes']), (180, 84))
            restored.record_run(points=500)
            plan = forecast(restored)
            self.assertEqual((restored.summary()['normal'], plan['needed_tickets'], plan['play_minutes']),
                             (500, 2, 24))

    def test_playtime_handles_no_point_pace_expired_deadline_and_invalid_preferences(self):
        with tempfile.TemporaryDirectory() as folder:
            ledger = Ledger(Path(folder) / 'runs.db')
            ledger.configure(rank=990, deadline='2026-10-19', normal_points=180, first_points=180)
            expired = forecast(ledger, date(2026, 10, 20))
            self.assertEqual((expired['play_minutes'], expired['daily_session_minutes']), (120, None))
            ledger.record_run(points=0)
            unknown = forecast(ledger, date(2026, 10, 20))
            self.assertIsNone(unknown['play_minutes'])
            self.assertIsNone(unknown['session_minutes'])
            self.assertIsNone(unknown['daily_play_minutes'])
            for changes in ({'run_minutes': 0}, {'run_minutes': 16}, {'run_minutes': 12.5},
                            {'run_minutes': True}, {'extra_minutes': -1}, {'extra_minutes': 1.5}):
                with self.assertRaises(ValueError):
                    ledger.configure(**changes)
            self.assertEqual((ledger.settings()['run_minutes'], ledger.settings()['extra_minutes']), (12, 0))

    def test_playtime_preferences_include_optional_overhead_and_persist(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'runs.db'
            ledger = Ledger(path)
            ledger.configure(rank=990, normal_points=180, first_points=180, daily_tickets=0,
                             deadline='2026-10-29', run_minutes=15, extra_minutes=3)
            restored = Ledger(path)
            plan = forecast(restored, date(2026, 10, 20))
            self.assertEqual((plan['play_minutes'], plan['session_minutes'],
                              plan['daily_session_minutes']), (150, 180, 18))
            ledger.correct_stats(rank=1000)
            done = forecast(ledger, date(2026, 10, 20))
            self.assertEqual((done['play_minutes'], done['session_minutes']), (0, 0))

    def test_remaining_playtime_uses_twelve_minutes_and_updates_after_results(self):
        with tempfile.TemporaryDirectory() as folder:
            ledger = Ledger(Path(folder) / 'runs.db')
            ledger.configure(rank=990, normal_points=180, first_points=180,
                             daily_tickets=0, deadline='2026-10-29')
            plan = forecast(ledger, date(2026, 10, 20))
            self.assertEqual((plan['needed_tickets'], plan['play_minutes'],
                              plan['full_run_minutes'], plan['daily_play_minutes']),
                             (10, 120, 150, 12))
            ledger.record_run(points=180)
            self.assertEqual(forecast(ledger, date(2026, 10, 20))['play_minutes'], 108)

    def test_editing_checkpointed_and_included_runs_only_corrects_history(self):
        with tempfile.TemporaryDirectory() as folder:
            ledger = Ledger(Path(folder) / 'runs.db')
            old = ledger.record_run(points=180, money=200000, expenses=10000)
            ledger.correct_stats(rank=184, rank_points=53, tickets=99, coins=9637500,
                                 lifetime_points=47723)
            included = ledger.record_run(points=192, money=431719, applied=False)
            ledger.update_run(old, points=400, money=None, expenses=50000, consumes_ticket=False)
            ledger.update_run(included, points=200, money=500000)
            state = ledger.summary()
            self.assertEqual((state['rank'], state['rank_points'], state['tickets'],
                              state['coins'], state['lifetime_points'], state['loot_value'],
                              state['loot_unknown_runs']), (184, 53, 99, 9637500, 47723, 500000, 1))
            ledger.update_run(included, applied=True)
            self.assertEqual((ledger.summary()['rank'], ledger.summary()['rank_points'],
                              ledger.summary()['tickets'], ledger.summary()['lifetime_points']),
                             (185, 73, 98, 47923))
            ledger.update_run(included, applied=False)
            self.assertEqual((ledger.summary()['rank'], ledger.summary()['tickets']), (184, 99))

    def test_invalid_run_edits_are_atomic_and_ticket_changes_use_only_the_difference(self):
        with tempfile.TemporaryDirectory() as folder:
            ledger = Ledger(Path(folder) / 'runs.db')
            ledger.configure(tickets=1)
            run = ledger.record_run(points=180, money=0)
            ledger.update_run(run, points=200)
            self.assertEqual(ledger.summary()['tickets'], 0)
            free = ledger.record_run(points=0, consumes_ticket=False)
            original = ledger.runs()
            for changes in ({'points': 1.5}, {'money': 1.5}, {'expenses': True},
                            {'day': '2026-02-30'}, {'applied': 2}, {'notes': None},
                            {'start_id': 123}, {'points': 400, 'consumes_ticket': True}):
                with self.assertRaises(ValueError):
                    ledger.update_run(free, **changes)
                self.assertEqual(ledger.runs(), original)
            with self.assertRaises(ValueError):
                ledger.update_run(999999, points=1)
            ledger.update_run(run, consumes_ticket=False)
            ledger.update_run(free, consumes_ticket=True)
            self.assertEqual(ledger.summary()['tickets'], 0)

    def test_edit_saved_run_updates_totals_and_preserves_evidence_and_active_run(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'runs.db'
            ledger = Ledger(path)
            start = ledger.start_run(1000000)
            run = ledger.record_run(points=180, start_id=start, money_image='loot.png',
                                    points_image='points.png', source_key='result-1')
            original = ledger.runs()[0]
            active = ledger.start_run()
            ledger.save_draft({'points': '192', 'notes': 'Next run'})
            ledger.update_run(run, points=360, money=500000, expenses=40000,
                              day='2026-10-19', notes='Corrected result', consumes_ticket=False)
            restored = Ledger(path)
            row = restored.runs()[0]
            self.assertEqual((row['id'], row['points'], row['money'], row['expenses'],
                              row['day'], row['notes'], row['consumes_ticket']),
                             (run, 360, 500000, 40000, '2026-10-19', 'Corrected result', 0))
            self.assertEqual((row['timestamp'], row['start_id'], row['source_key'],
                              row['money_image'], row['points_image']),
                             (original['timestamp'], start, 'result-1', 'loot.png', 'points.png'))
            state = restored.summary(date(2026, 10, 19))
            self.assertEqual((state['rank'], state['rank_points'], state['tickets'],
                              state['coins'], state['loot_value'], state['today_points']),
                             (179, 0, 105, 960000, 500000, 360))
            self.assertEqual(restored.active_start()['id'], active)
            self.assertEqual(restored.draft(), {'points': '192', 'notes': 'Next run'})
            self.assertEqual(len(restored.runs()), 1)

    def test_old_balance_corrections_survive_reward_support_upgrade(self):
        import sqlite3
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'old.db'
            with sqlite3.connect(path) as db:
                db.execute('CREATE TABLE corrections(id INTEGER PRIMARY KEY,timestamp TEXT,rank INTEGER,rank_points INTEGER,tickets INTEGER,coins INTEGER,run_cutoff INTEGER,purchase_cutoff INTEGER,spending_cutoff INTEGER,reason TEXT,approximate INTEGER,estimated INTEGER DEFAULT 0)')
                db.execute("INSERT INTO corrections VALUES(1,'2026-10-19',184,53,99,9637500,0,0,0,'Original balance',0,0)")
            db.close()
            ledger=Ledger(path)
            self.assertEqual((ledger.summary()['tickets'],ledger.summary()['coins']),(99,9637500))
            ledger.award_tickets(2)
            ledger.correct_stats(rank=185)
            self.assertEqual(ledger.summary()['tickets'],101)
            ledger.award_tickets(1)
            self.assertEqual(Ledger(path).summary()['tickets'],102)
            self.assertEqual(ledger.corrections()[-1]['reason'],'Original balance')

    def test_invalid_ticket_rewards_leave_stock_unchanged(self):
        with tempfile.TemporaryDirectory() as folder:
            ledger=Ledger(Path(folder)/'runs.db')
            for count in (0,-1,1.5,True):
                with self.assertRaises(ValueError):ledger.award_tickets(count)
            with self.assertRaises(ValueError):ledger.award_tickets(1,day='invalid')
            self.assertEqual(ledger.summary()['tickets'],105)
            self.assertEqual(ledger.ticket_rewards(),[])

    def test_chest_tickets_do_not_cost_coins_or_use_paid_shop_slots(self):
        with tempfile.TemporaryDirectory() as folder:
            ledger=Ledger(Path(folder)/'runs.db')
            ledger.correct_stats(coins=1000000)
            before=forecast(ledger)
            ledger.award_tickets(3,source='Sanctum chest')
            state=ledger.summary()
            self.assertEqual((state['tickets'],state['coins'],state['bought_today']),(108,1000000,0))
            self.assertEqual(forecast(ledger)['available_tickets'],before['available_tickets']+3)
            self.assertEqual(ledger.buy(1),20000)
            ledger.record_run(points=180)
            self.assertEqual(ledger.summary()['tickets'],108)
            ledger.correct_stats(coins=900000)
            self.assertEqual(ledger.summary()['tickets'],108,'A correction already includes previous rewards')
            ledger.award_tickets(2)
            self.assertEqual(ledger.buy(1),50000)
            restored=Ledger(Path(folder)/'runs.db')
            state=restored.summary()
            self.assertEqual((state['tickets'],state['coins'],state['bought_today']),(111,850000,2))
            self.assertEqual(restored.ticket_rewards()[-1]['source'],'Sanctum chest')

    def test_points_only_run_keeps_loot_unknown_and_wallet_unchanged(self):
        with tempfile.TemporaryDirectory() as folder:
            ledger=Ledger(Path(folder)/'runs.db')
            ledger.correct_stats(coins=900000)
            unknown=ledger.record_run(points=180)
            ledger.record_run(points=0,money=0)
            ledger.record_run(points=0,money=350000)
            self.assertIsNone(next(r for r in ledger.runs() if r['id']==unknown)['money'])
            state=ledger.summary()
            self.assertEqual(state['coins'],900000)
            self.assertEqual(state['rank'],178)
            self.assertEqual(state['tickets'],102)
            self.assertEqual(state['loot_value'],350000)
            self.assertEqual(state['loot_unknown_runs'],1)
            self.assertIsNone(state['run_net'])

    def test_start_without_balance_preserves_wallet_until_result_saved(self):
        with tempfile.TemporaryDirectory() as folder:
            ledger=Ledger(Path(folder)/'runs.db')
            ledger.correct_stats(coins=900000)
            ledger.spend(120000)
            before=ledger.summary()
            observations=len(ledger.corrections())
            start=ledger.start_run()
            self.assertIsNone(ledger.active_start()['balance'])
            self.assertEqual(ledger.summary(),before)
            self.assertEqual(len(ledger.corrections()),observations)
            restored=Ledger(Path(folder)/'runs.db')
            self.assertEqual(restored.active_start()['id'],start)
            with self.assertRaises(ValueError):restored.start_run()
            restored.record_run(points=180,money=400000,start_id=start)
            self.assertIsNone(restored.active_start())
            self.assertEqual(restored.summary()['coins'],780000)
            self.assertEqual(restored.summary()['tickets'],104)
            self.assertEqual(restored.summary()['rank'],178)

    def test_fifteen_daily_tickets_cost_2740000(self):
        self.assertEqual(ticket_cost(15), 2740000)

    def test_recorded_points_are_not_doubled_again_and_persist(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'runs.db'
            ledger = Ledger(path)
            ledger.record_run(points=360, money=400000, expenses=80000, bonus=True,
                              day='2026-10-18')
            ledger = Ledger(path)
            state = ledger.summary(date(2026, 10, 18))
            self.assertEqual((state['rank'], state['rank_points'], state['tickets'],
                              state['run_net']), (179, 0, 104, 320000))

    def test_last_day_bonus_and_ticket_inventory(self):
        with tempfile.TemporaryDirectory() as folder:
            ledger = Ledger(Path(folder) / 'runs.db')
            ledger.configure(rank=0, target=3, tickets=1, daily_tickets=1,
                             deadline='2026-10-19', normal_points=100, first_points=200)
            result = forecast(ledger, date(2026, 10, 18))
            self.assertEqual((result['reachable'], result['points'], result['needed_tickets']),
                             (False, 500, 4))

    def test_split_purchases_follow_daily_tiers_and_deletion_restores_ticket(self):
        with tempfile.TemporaryDirectory() as folder:
            ledger = Ledger(Path(folder) / 'runs.db')
            self.assertEqual(ledger.buy(3, '2026-10-18'), 140000)
            self.assertEqual(ledger.buy(12, '2026-10-18'), 2600000)
            run_id = ledger.record_run(points=0, money=0, expenses=80000, day='2026-10-18')
            self.assertEqual(ledger.summary(date(2026,10,18))['tickets'], 119)
            ledger.delete_run(run_id)
            self.assertEqual(ledger.summary(date(2026,10,18))['tickets'], 120)

    def test_zero_point_completed_runs_do_not_predict_success(self):
        with tempfile.TemporaryDirectory() as folder:
            ledger = Ledger(Path(folder) / 'runs.db')
            ledger.record_run(points=0, money=0, day='2026-10-18', bonus=True)
            result = forecast(ledger, date(2026,10,18))
            self.assertFalse(result['reachable'])
            self.assertIsNone(result['needed_tickets'])

    def test_between_run_spending_persists_without_consuming_a_ticket(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'runs.db'
            ledger = Ledger(path)
            ledger.configure(starting_coins=1000000)
            ledger.record_run(points=400, money=500000, day='2026-10-18')
            expense_id = ledger.spend(120000, note='New gear', day='2026-10-18')
            ledger = Ledger(path)
            state = ledger.summary(date(2026, 10, 18))
            self.assertEqual((state['coins'], state['today_net'], state['tickets']),
                             (880000, -120000, 104))
            self.assertEqual(ledger.spending()[0]['note'], 'New gear')
            ledger.delete_spending(expense_id)
            self.assertEqual(ledger.summary()['coins'], 1000000)

    def test_current_stat_correction_preserves_history_and_counts_only_new_runs(self):
        with tempfile.TemporaryDirectory() as folder:
            ledger = Ledger(Path(folder) / 'runs.db')
            ledger.record_run(points=192, money=431719)
            ledger.correct_stats(rank=184, rank_points=53, tickets=99, coins=9637500,
                                 lifetime_points=47723)
            self.assertEqual(len(ledger.runs()), 1)
            ledger.record_run(points=200, money=500000)
            state = Ledger(Path(folder) / 'runs.db').summary()
            self.assertEqual((state['rank'], state['rank_points'], state['tickets'],
                              state['coins'], state['lifetime_points'], state['remaining']),
                             (185, 73, 98, 9637500, 47923, 146627))

    def test_start_balance_supersedes_sales_and_spending_without_crediting_loot(self):
        with tempfile.TemporaryDirectory() as folder:
            ledger = Ledger(Path(folder) / 'runs.db')
            start = ledger.start_run(9637500, approximate=True)
            ledger.record_run(points=192, money=431719, start_id=start)
            self.assertEqual(ledger.summary()['coins'], 9637500)
            ledger.spend(120000)
            self.assertEqual(ledger.summary()['coins'], 9517500)
            ledger.start_run(10000000)
            ledger = Ledger(Path(folder) / 'runs.db')
            self.assertEqual((ledger.summary()['coins'], ledger.summary()['loot_value'],
                              ledger.summary()['tickets']), (10000000, 431719, 104))
            self.assertIsNotNone(ledger.active_start())

    def test_historical_run_already_in_baseline_only_adds_history(self):
        with tempfile.TemporaryDirectory() as folder:
            ledger = Ledger(Path(folder) / 'runs.db')
            ledger.configure(rank=184, rank_points=53, tickets=99, starting_coins=9637500)
            first = ledger.record_run(points=192, money=431719, applied=False, source_key='sample')
            second = ledger.record_run(points=192, money=431719, applied=False, source_key='sample')
            state = ledger.summary()
            self.assertEqual((state['rank'],state['rank_points'],state['tickets'],state['coins']),
                             (184,53,99,9637500))
            self.assertEqual(first, second)
            self.assertEqual(len(ledger.runs()), 1)

    def test_buying_on_a_day_without_playing_keeps_the_tickets(self):
        with tempfile.TemporaryDirectory() as folder:
            ledger = Ledger(Path(folder) / 'runs.db')
            ledger.buy(15, day='2026-10-18')
            state = ledger.summary(date(2026,10,19))
            self.assertEqual((state['tickets'],state['rank'],state['rank_points'],
                              state['today_runs'],state['normal']), (120,177,0,0,190))
            self.assertEqual(len(ledger.runs()), 0)

    def test_screenshot_awards_are_used_directly_without_bonus_labels(self):
        with tempfile.TemporaryDirectory() as folder:
            ledger = Ledger(Path(folder) / 'runs.db')
            ledger.configure(deadline='2026-10-18', daily_tickets=0)
            ledger.record_run(points=400, money=0, day='2026-10-18')
            ledger.record_run(points=200, money=0, day='2026-10-18')
            state = ledger.summary(date(2026,10,18))
            self.assertEqual((state['rank'], state['rank_points'], state['normal']),
                             (180, 60, 300))
            self.assertEqual(forecast(ledger, date(2026,10,18))['points'], 30900)


if __name__ == '__main__':
    unittest.main()
