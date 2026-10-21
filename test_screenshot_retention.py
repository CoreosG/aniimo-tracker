import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
from tracker_core import Ledger
from screenshot_retention import prune_screenshots


class ScreenshotRetentionTests(unittest.TestCase):
    def test_shared_files_stay_until_the_newest_reference_expires(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);folder=root/'screenshots';folder.mkdir();ledger=Ledger(root/'tracker.db')
            ledger.configure(screenshot_runs=1)
            shared=folder/'shared.png';shared.touch()
            ledger.record_run(points=180,points_image=str(shared))
            ledger.record_run(points=190,money_image=str(shared))
            prune_screenshots(ledger,folder);self.assertTrue(shared.exists())
            ledger.record_run(points=200)  # A points-only run still counts.
            prune_screenshots(ledger,folder);self.assertFalse(shared.exists())

    def test_locked_file_is_reported_without_removing_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);folder=root/'screenshots';folder.mkdir();ledger=Ledger(root/'tracker.db')
            ledger.configure(screenshot_runs=0)
            old=folder/'old.png';old.touch();ledger.record_run(points=180,points_image=str(old))
            with patch('pathlib.Path.unlink',side_effect=PermissionError('in use')):
                result=prune_screenshots(ledger,folder)
            self.assertEqual(result['removed'],0);self.assertEqual(result['failed'],[str(old)])
            self.assertTrue(old.exists());self.assertEqual(len(ledger.runs()),1)

    def test_default_keeps_last_30_runs_without_removing_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);folder=root/'screenshots';folder.mkdir();ledger=Ledger(root/'tracker.db')
            files=[]
            for number in range(31):
                path=folder/f'{number}.png';path.write_bytes(b'capture');files.append(path)
                ledger.record_run(points=180,points_image=str(path),applied=False)
            before=ledger.runs();summary=ledger.summary()
            result=prune_screenshots(ledger,folder)
            self.assertEqual(result['removed'],1)
            self.assertFalse(files[0].exists());self.assertTrue(all(p.exists() for p in files[1:]))
            self.assertEqual(ledger.runs(),before);self.assertEqual(ledger.summary(),summary)

    def test_balance_draft_active_shared_and_external_paths_are_safe(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);folder=root/'screenshots';folder.mkdir();ledger=Ledger(root/'tracker.db')
            ledger.configure(screenshot_runs=1)
            def image(name):
                p=folder/name;p.write_bytes(b'capture');return str(p)
            old_balance=image('old-balance.png');old_points=image('old-points.png')
            external=root/'external.png';external.write_bytes(b'external')
            start=ledger.start_run(None,old_balance)
            ledger.record_run(points=180,points_image=old_points,money_image=str(external),start_id=start)
            shared=image('shared.png');start=ledger.start_run(None,image('new-balance.png'))
            ledger.record_run(points=180,points_image=shared,start_id=start)
            active=image('active.png');ledger.start_run(None,active)
            draft=image('draft.png');ledger.save_draft({'images':{'money':draft}})
            inflight=image('inflight.png');orphan=image('20261021_120000_1234abcd_auto.png')
            manual=image('my-manual-image.png')
            nested=folder/'nested';nested.mkdir();(nested/'manual.png').write_bytes(b'keep')
            before=ledger.summary()
            prune_screenshots(ledger,folder,protected=[inflight])
            self.assertFalse(Path(old_balance).exists());self.assertFalse(Path(old_points).exists());self.assertFalse(Path(orphan).exists())
            for p in (external,shared,active,draft,inflight,manual,nested/'manual.png'):self.assertTrue(Path(p).exists(),str(p))
            self.assertEqual(ledger.summary(),before)

    def test_zero_keeps_no_saved_screenshots_but_preserves_unsaved_work(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);folder=root/'screenshots';folder.mkdir();ledger=Ledger(root/'tracker.db')
            ledger.configure(screenshot_runs=0)
            saved=folder/'saved.png';saved.touch();draft=folder/'draft.png';draft.touch()
            ledger.record_run(points=-140,points_image=str(saved))
            ledger.save_draft({'images':{'points':str(draft)}})
            prune_screenshots(ledger,folder)
            self.assertFalse(saved.exists());self.assertTrue(draft.exists())
            self.assertEqual(len(ledger.runs()),1)
            for invalid in (-1,1.5,True):
                with self.assertRaises(ValueError):ledger.configure(screenshot_runs=invalid)
