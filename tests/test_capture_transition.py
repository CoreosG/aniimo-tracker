import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from app import App


class CaptureTransitionTests(unittest.TestCase):
    def test_shop_coin_balance_uses_wallet_crop_not_other_currency_or_item_prices(self):
        with tempfile.TemporaryDirectory() as directory,patch('sanctum_panel.game_is_foreground',return_value=False):
            app=App(directory,hotkeys=False)
            try:
                screenshot=Path(directory)/'screenshots/shop.png'
                Image.new('RGB',(1920,1080)).save(screenshot)
                def ocr(path,region=None):
                    return '6 214 628' if region else 'Loja\n678\n6 214 628\nEquipamento\nBilhete do Caos\n400.0 K\nComprar'
                with patch('app.recognize',side_effect=ocr):
                    app.auto_attach(screenshot)
                    deadline=time.monotonic()+5
                    while (app.auto_busy or app.pending_ocr) and time.monotonic()<deadline:
                        app.update();time.sleep(.01)
                self.assertEqual(app.ledger.active_start()['balance'],6214628)
                self.assertEqual(app.ledger.summary()['coins'],6214628)
            finally:app.close()

    def test_inventory_during_active_run_refreshes_wallet_without_replacing_start(self):
        with tempfile.TemporaryDirectory() as directory,patch('sanctum_panel.game_is_foreground',return_value=False):
            app=App(directory,hotkeys=False)
            try:
                app.fields['balance'].set('7000000');app.begin_run(manual=True)
                active=app.ledger.active_start();tickets=app.ledger.summary()['tickets']
                app.fields['money'].set('400000');app.fields['points'].set('180')
                screenshot=Path(directory)/'screenshots/inventory.png'
                Image.new('RGB',(640,480)).save(screenshot)
                def ocr(path,region=None):
                    return 'Inventário\nMochila de Aventura\nCofre' if region is None else '6214.6 K'
                with patch('app.recognize',side_effect=ocr):
                    app.auto_attach(screenshot)
                    deadline=time.monotonic()+5
                    while (app.auto_busy or app.pending_ocr) and time.monotonic()<deadline:
                        app.update();time.sleep(.01)
                self.assertEqual(app.ledger.summary()['coins'],6214600)
                self.assertEqual(app.ledger.active_start(),active)
                self.assertEqual(app.ledger.summary()['tickets'],tickets)
                self.assertEqual(app.fields['money'].get(),'400000')
                self.assertEqual(app.fields['points'].get(),'180')
            finally:app.close()

    def test_gameplay_capture_starts_without_balance_during_map_only(self):
        with tempfile.TemporaryDirectory() as directory,patch('sanctum_panel.game_is_foreground',return_value=False):
            app=App(directory,hotkeys=False)
            try:
                app.sanctum.watch_action()
                screenshot=Path(directory)/'screenshots/gameplay.png'
                Image.new('RGB',(640,480)).save(screenshot)
                with patch('app.recognize',return_value=''):
                    app.auto_attach(screenshot)
                    deadline=time.monotonic()+8
                    while (app.auto_busy or app.pending_ocr) and time.monotonic()<deadline:
                        app.update();time.sleep(.01)
                self.assertIsNotNone(app.ledger.active_start(),app.status.get())
                self.assertIsNone(app.ledger.active_start()['balance'])
                self.assertFalse(app.sanctum.session.standalone)
            finally:app.close()

    def test_explicit_manual_points_save_also_exits_map_only(self):
        with tempfile.TemporaryDirectory() as directory,patch('sanctum_panel.game_is_foreground',return_value=False):
            app=App(directory,hotkeys=False)
            try:
                app.sanctum.watch_action();app.fields['points'].set('170')
                self.assertTrue(app.quick_save_run())
                self.assertFalse(app.sanctum.session.standalone)
                self.assertEqual(app.ledger.runs()[0]['points'],170)
            finally:app.close()

    def test_inventory_and_result_capture_burst_stays_with_automatic_run_start(self):
        with tempfile.TemporaryDirectory() as directory,patch('sanctum_panel.game_is_foreground',return_value=False):
            app=App(directory,hotkeys=False)
            try:
                app.sanctum.watch_action()
                paths=[Path(directory)/'screenshots'/name for name in ('inventory.png','points.png')]
                for path in paths:Image.new('RGB',(640,480)).save(path)
                def ocr(path,region=None):
                    if Path(path).name=='points.png':return 'Pontos de ranque\n10000/10200\n+170'
                    return '7654.0 K' if region is not None else 'Inventário\nMochila de Aventura\nCofre'
                with patch('app.recognize',side_effect=ocr):
                    for path in paths:app.auto_attach(path)
                    deadline=time.monotonic()+5
                    while (app.auto_busy or app.auto_pending or app.pending_ocr) and time.monotonic()<deadline:
                        app.update();time.sleep(.01)
                self.assertEqual(app.ledger.active_start()['balance'],7654000)
                self.assertEqual(app.fields['points'].get(),'170',app.status.get())
                self.assertEqual(app.fields['lifetime'].get(),'10000')
                self.assertEqual(set(app.draft_images),{'balance','points'})
            finally:app.close()

    def test_inventory_capture_starts_a_balanced_run_from_map_only(self):
        with tempfile.TemporaryDirectory() as directory,patch('sanctum_panel.game_is_foreground',return_value=False):
            app=App(directory,hotkeys=False)
            try:
                app.sanctum.watch_action()
                baseline=app.ledger.summary()
                screenshot=Path(directory)/'screenshots/inventory.png'
                Image.new('RGB',(640,480)).save(screenshot)
                def ocr(path,region=None):
                    return 'Inventário\nMochila de Aventura\nCofre' if region is None else '7654.0 K'
                with patch('app.recognize',side_effect=ocr):
                    app.auto_attach(screenshot)
                    deadline=time.monotonic()+4
                    while (app.auto_busy or app.pending_ocr) and time.monotonic()<deadline:
                        app.update();time.sleep(.01)
                active=app.ledger.active_start()
                self.assertIsNotNone(active,app.status.get())
                self.assertEqual(active['balance'],7654000)
                self.assertFalse(app.sanctum.session.standalone)
                self.assertEqual(app.ledger.summary()['tickets'],baseline['tickets'])
                self.assertEqual(app.draft_images['balance'],str(screenshot))
            finally:app.close()

    def test_points_capture_leaves_map_only_and_can_save_points_only(self):
        with tempfile.TemporaryDirectory() as directory,patch('sanctum_panel.game_is_foreground',return_value=False):
            app=App(directory,hotkeys=False)
            try:
                app.sanctum.watch_action()
                screenshot=Path(directory)/'screenshots/points.png'
                Image.new('RGB',(640,480)).save(screenshot)
                with patch('app.recognize',return_value='Imperador dos Ovos\n47723/47850\n+192'):
                    app.auto_attach(screenshot)
                    deadline=time.monotonic()+4
                    while (app.auto_busy or app.pending_ocr) and time.monotonic()<deadline:
                        app.update();time.sleep(.01)
                self.assertFalse(app.sanctum.session.standalone)
                self.assertEqual(app.fields['points'].get(),'192')
                self.assertTrue(app.quick_save_run())
                self.assertEqual(app.ledger.runs()[0]['points'],192)
                self.assertIsNone(app.ledger.runs()[0]['money'])
            finally:app.close()
