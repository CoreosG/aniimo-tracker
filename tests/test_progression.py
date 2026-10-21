import tempfile
import unittest
import json
import sqlite3
from contextlib import closing
from pathlib import Path

from tracker_core import Ledger


class ProgressionTests(unittest.TestCase):
    def test_known_total_floors_each_award_at_zero_in_recorded_order(self):
        with tempfile.TemporaryDirectory() as folder:
            ledger=Ledger(Path(folder)/'tracker.db')
            ledger.correct_stats(lifetime_points=0)
            ledger.record_run(points=-140)
            self.assertEqual(ledger.summary()['total_points'],0)
            ledger.record_run(points=170)
            self.assertEqual(ledger.summary()['total_points'],170)
            ledger.record_run(points=-200)
            ledger.correct_stats(coins=7654000)
            self.assertEqual(ledger.corrections()[0]['lifetime_points'],0)
            ledger.record_run(points=190)
            self.assertEqual(ledger.summary()['total_points'],190)
            self.assertEqual(ledger.summary()['today_points'],20,
                             'Flooring progression must not rewrite recorded award values')

    def test_total_points_cross_the_emperor_threshold_in_both_directions(self):
        with tempfile.TemporaryDirectory() as folder:
            ledger = Ledger(Path(folder) / 'tracker.db')
            ledger.correct_stats(lifetime_points=14000)
            state = ledger.summary()
            self.assertEqual(state['emperor_threshold'], 14550)
            self.assertEqual((state['rank'], state['eggs'], state['rank_points']), (0, 0, 0))
            self.assertFalse(state['is_emperor'])
            self.assertEqual((state['lifetime_points'], state['total_points'], state['remaining']),
                             (14000, 14000, 180550))
            ledger.record_run(points=550)
            state = ledger.summary()
            self.assertTrue(state['is_emperor'])
            self.assertEqual((state['eggs'], state['rank_points'], state['lifetime_points']), (0, 0, 14550))
            ledger.record_run(points=180)
            state = ledger.summary()
            self.assertEqual((state['eggs'], state['rank_points'], state['lifetime_points']), (1, 0, 14730))
            ledger.record_run(points=-181)
            state = ledger.summary()
            self.assertFalse(state['is_emperor'])
            self.assertEqual((state['eggs'], state['rank_points'], state['lifetime_points']), (0, 0, 14549))
            self.assertEqual(state['remaining'], 180001)

    def test_cash_and_ticket_checkpoints_keep_known_pre_emperor_total(self):
        with tempfile.TemporaryDirectory() as folder:
            ledger = Ledger(Path(folder) / 'tracker.db')
            ledger.correct_stats(lifetime_points=14000, coins=7000000)
            old = ledger.record_run(points=200)
            ledger.correct_stats(tickets=40)
            ledger.start_run(7654000)
            ledger.update_run(old, points=999)
            state = ledger.summary()
            self.assertEqual((state['lifetime_points'], state['eggs'], state['tickets'], state['coins']),
                             (14200, 0, 40, 7654000))
            self.assertTrue(all(row['lifetime_points'] is not None for row in ledger.corrections()))
            self.assertIsNone(ledger.settings()['lifetime_offset'])

    def test_calibration_and_later_threshold_changes_preserve_observed_total(self):
        with tempfile.TemporaryDirectory() as folder:
            ledger = Ledger(Path(folder) / 'tracker.db')
            ledger.correct_stats(rank=184, rank_points=53, lifetime_points=47723)
            self.assertEqual(ledger.settings()['lifetime_offset'], 14550)
            ledger.configure(lifetime_offset=15000)
            state = ledger.summary()
            self.assertEqual((state['lifetime_points'], state['eggs'], state['rank_points']), (47723, 181, 143))
            ledger.correct_stats(lifetime_points=14999)
            self.assertEqual(ledger.summary()['emperor_threshold'], 15000)
            self.assertFalse(ledger.summary()['is_emperor'])
            ledger.correct_stats(rank=2, rank_points=10)
            self.assertEqual(ledger.summary()['lifetime_points'], 15370)

    def test_unknown_legacy_total_and_known_zero_are_distinct(self):
        with tempfile.TemporaryDirectory() as folder:
            ledger = Ledger(Path(folder) / 'tracker.db')
            legacy = ledger.summary()
            self.assertEqual(legacy['rank'], 177)
            self.assertIsNone(legacy['lifetime_points'])
            self.assertIsNone(legacy['is_emperor'])
            ledger.correct_stats(coins=1000000)
            self.assertIsNone(ledger.summary()['lifetime_points'])
            ledger.correct_stats(lifetime_points=0)
            ledger.correct_stats(tickets=5)
            self.assertEqual(ledger.summary()['lifetime_points'], 0)
            self.assertEqual(ledger.summary()['remaining'], 194550)
            self.assertFalse(ledger.summary()['is_emperor'])

    def test_invalid_thresholds_and_inconsistent_calibration_do_not_change_stats(self):
        with tempfile.TemporaryDirectory() as folder:
            ledger = Ledger(Path(folder) / 'tracker.db')
            ledger.correct_stats(lifetime_points=14000)
            before = ledger.summary()
            for threshold in (-1, True, '14550'):
                with self.assertRaises(ValueError):
                    ledger.configure(lifetime_offset=threshold)
            with self.assertRaises(ValueError):
                ledger.correct_stats(rank=184, rank_points=53, lifetime_points=100)
            self.assertEqual(ledger.summary(), before)

    def test_legacy_calibrated_checkpoint_migrates_without_reinterpreting_its_total(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'tracker.db'
            with closing(sqlite3.connect(path)) as db, db:
                db.execute('CREATE TABLE settings(id INTEGER PRIMARY KEY,value TEXT NOT NULL)')
                db.execute('INSERT INTO settings VALUES(1,?)', (json.dumps(dict(rank=184, rank_points=53, lifetime_offset=14550)),))
                db.execute('''CREATE TABLE corrections(id INTEGER PRIMARY KEY,timestamp TEXT,rank INTEGER,rank_points INTEGER,
                    tickets INTEGER,coins INTEGER,run_cutoff INTEGER,purchase_cutoff INTEGER,spending_cutoff INTEGER,
                    reason TEXT,approximate INTEGER,estimated INTEGER DEFAULT 0)''')
                db.execute("INSERT INTO corrections VALUES(1,'2026-10-20T12:00:00',184,53,99,7654000,0,0,0,'Existing',0,0)")
            ledger = Ledger(path)
            self.assertEqual(ledger.corrections()[0]['lifetime_points'], 47723)
            self.assertEqual((ledger.summary()['rank'], ledger.summary()['rank_points']), (184, 53))
            ledger.configure(lifetime_offset=15000)
            reloaded = Ledger(path)
            self.assertEqual(reloaded.summary()['lifetime_points'], 47723)
            self.assertEqual(reloaded.summary()['coins'], 7654000)
            self.assertEqual(reloaded.corrections()[0]['timestamp'], '2026-10-20T12:00:00')
