import tempfile
import unittest
from datetime import date, datetime
from unittest.mock import patch
from pathlib import Path

from tracker_core import Ledger


class AnalyticsTests(unittest.TestCase):
    def test_export_keeps_unknown_values_blank_and_does_not_export_unselected_runs(self):
        import csv
        from analytics import build_report, export_runs_csv
        with tempfile.TemporaryDirectory() as folder:
            ledger=Ledger(Path(folder)/'runs.db')
            ledger.record_run(points=200,money=999999,day='2026-10-01')
            ledger.record_run(points=-140,day='2026-10-20')
            ledger.record_run(points=180,money=0,day='2026-10-20')
            report=build_report(ledger,days=1,today=date(2026,10,20))
            path=Path(folder)/'report.csv'
            export_runs_csv(report,path)
            with path.open(encoding='utf-8-sig',newline='') as stream:
                rows=list(csv.DictReader(stream))
            self.assertEqual(len(rows),2)
            self.assertEqual([row['loot_value'] for row in rows],['0',''])
            self.assertEqual([row['points'] for row in rows],['180','-140'])
            self.assertEqual(rows[1]['modeled_margin_not_cash_profit'],'')
            self.assertEqual(report['performance']['known_ticketed_loot'],1)

    def test_performance_uses_known_ticketed_loot_and_estimated_time_not_cash_profit(self):
        from analytics import build_report
        with tempfile.TemporaryDirectory() as folder:
            ledger=Ledger(Path(folder)/'runs.db')
            ledger.configure(daily_tickets=1,gear_slots=0,solo_keys=0,run_minutes=12,extra_minutes=3)
            first=ledger.record_run(points=200,money=500000,day='2026-10-20')
            ledger.record_run(points=-140,money=100000,day='2026-10-20')
            ledger.record_run(points=180,day='2026-10-20')
            ledger.record_run(points=50,money=900000,consumes_ticket=False,day='2026-10-20')
            before=ledger.summary()
            report=build_report(ledger,days=1,today=date(2026,10,20))
            performance=report['performance']
            self.assertEqual(performance['ticketed_runs'],3)
            self.assertEqual(performance['known_ticketed_loot'],2)
            self.assertEqual(performance['estimated_minutes'],45)
            self.assertEqual(performance['average_loot'],300000)
            self.assertEqual(performance['loot_per_hour'],1200000)
            self.assertEqual(performance['planned_cost_per_run'],20000)
            self.assertEqual(performance['average_modeled_margin'],280000)
            self.assertEqual(performance['median_points'],190)
            self.assertEqual(performance['points_per_hour'],320)
            row=next(row for row in report['runs'] if row['id']==first)
            self.assertEqual((row['modeled_cost'],row['modeled_margin']),(20000,480000))
            self.assertIsNone(report['runs'][0]['modeled_margin'])
            self.assertEqual(ledger.summary(),before)

    def test_filters_include_buy_only_days_and_empty_periods_have_no_invented_loot(self):
        from analytics import build_report
        with tempfile.TemporaryDirectory() as folder:
            ledger=Ledger(Path(folder)/'runs.db')
            ledger.record_run(points=200,money=500000,day='2026-10-01')
            ledger.buy(3,day='2026-10-19')
            ledger.award_tickets(2,day='2026-10-19')
            recent=build_report(ledger,days=2,today=date(2026,10,20))
            self.assertEqual(recent['totals']['runs'],0)
            self.assertIsNone(recent['totals']['average_points'])
            self.assertEqual((recent['daily'][0]['bought'],recent['daily'][0]['free'],
                              recent['daily'][0]['used'],recent['daily'][0]['costs']), (3,2,0,140000))
            self.assertFalse(recent['wallet_known'])
            self.assertEqual(recent['wallet'],[])
            everything=build_report(ledger,days=None,today=date(2026,10,20))
            self.assertEqual((everything['start'],everything['totals']['loot']),('2026-10-01',500000))
            for days in (0,-1,1.5,True):
                with self.assertRaises(ValueError):build_report(ledger,days=days)

    def test_wallet_graph_uses_balance_checkpoints_not_loot_and_carries_range_start(self):
        from analytics import build_report
        with tempfile.TemporaryDirectory() as folder:
            ledger = Ledger(Path(folder) / 'runs.db')
            with patch('tracker_core.datetime') as clock:
                clock.now.return_value = datetime(2026,10,18,10)
                start = ledger.start_run(1000000)
                ledger.record_run(points=200,money=500000,start_id=start)
                clock.now.return_value = datetime(2026,10,19,10)
                start = ledger.start_run(1250000)
                ledger.record_run(points=200,start_id=start)
                ledger.spend(120000)
                ledger.buy(1)
            report = build_report(ledger,days=2,today=date(2026,10,19))
            self.assertEqual([point['coins'] for point in report['wallet']], [1000000,1250000])
            self.assertEqual(report['current_wallet'],1110000)
            self.assertEqual(report['wallet_change'],250000)
            one_day = build_report(ledger,days=1,today=date(2026,10,19))
            self.assertTrue(one_day['wallet'][0]['carried'])
            self.assertEqual(one_day['wallet'][0]['coins'],1000000)
            self.assertEqual(one_day['totals']['loot'],0)
            self.assertEqual(one_day['totals']['unknown_loot'],1)

    def test_daily_report_keeps_loot_costs_and_successful_point_pace_separate(self):
        from analytics import build_report
        with tempfile.TemporaryDirectory() as folder:
            ledger = Ledger(Path(folder) / 'runs.db')
            ledger.configure(starting_coins=1000000)
            ledger.record_run(points=200, money=500000, expenses=40000, day='2026-10-18')
            ledger.record_run(points=-140, day='2026-10-19')
            ledger.spend(120000, day='2026-10-19')
            ledger.buy(1, day='2026-10-19')
            ledger.award_tickets(3, day='2026-10-19')
            ledger.record_run(points=180, money=0, day='2026-10-20')
            before = ledger.summary()
            report = build_report(ledger, days=3, today=date(2026,10,20))
            totals = report['totals']
            self.assertEqual((totals['runs'],totals['failed'],totals['loot'],totals['unknown_loot'],
                              totals['costs'],totals['net_points'],totals['average_points']),
                             (3,1,500000,1,180000,240,190))
            self.assertEqual(report['current_wallet'],820000)
            day = report['daily'][1]
            self.assertEqual((day['day'],day['loot'],day['unknown_loot'],day['costs'],
                              day['gained'],day['lost'],day['bought'],day['free'],day['used']),
                             ('2026-10-19',None,1,140000,0,140,1,3,1))
            self.assertEqual(ledger.summary(),before,'Analytics must be read-only')

class CheckpointEditingTests(unittest.TestCase):
    def test_editing_the_latest_checkpoint_recalculates_cash_and_rejects_invalid_amounts(self):
        from tracker_core import Ledger
        with tempfile.TemporaryDirectory() as folder:
            ledger=Ledger(Path(folder)/'runs.db')
            checkpoint=ledger.correct_stats(coins=70000000)
            ledger.spend(120000)
            ledger.update_balance_checkpoint(checkpoint,7000000)
            self.assertEqual(ledger.summary()['coins'],6880000)
            for amount in (-1,1.5,True):
                with self.assertRaises(ValueError):ledger.update_balance_checkpoint(checkpoint,amount)
            self.assertEqual(ledger.summary()['coins'],6880000)

    def test_editing_an_old_wallet_checkpoint_removes_the_outlier_without_changing_current_stats(self):
        from tracker_core import Ledger
        from analytics import build_report
        with tempfile.TemporaryDirectory() as folder:
            ledger=Ledger(Path(folder)/'runs.db')
            checkpoint=ledger.correct_stats(coins=76540000)
            ledger.correct_stats(coins=10500000)
            active=ledger.start_run();ledger.save_draft({'points':'190'})
            baseline=ledger.summary();draft=ledger.draft();start=ledger.active_start()
            ledger.update_balance_checkpoint(checkpoint,7654000)
            self.assertEqual(len(ledger.corrections()),2)
            self.assertEqual(next(r for r in ledger.corrections() if r['id']==checkpoint)['coins'],7654000)
            self.assertNotIn(76540000,[p['coins'] for p in build_report(ledger,days=None)['wallet']])
            self.assertEqual(ledger.summary(),baseline)
            self.assertEqual(ledger.active_start(),start)
            self.assertEqual(ledger.draft(),draft)
