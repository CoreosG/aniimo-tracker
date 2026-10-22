import socket
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from app import App
from party_client import PartyClient
from map_engine import MapEngine
from tests.test_minimap_recognition import hud


class PartyNavigationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with socket.socket() as free:
            free.bind(('127.0.0.1',0));port=free.getsockname()[1]
        cls.url=f'ws://127.0.0.1:{port}/party'
        cls.relay=subprocess.Popen([sys.executable,str(Path(__file__).resolve().parents[1]/'src/party_server.py'),'--port',str(port)],
                                   stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)

    @classmethod
    def tearDownClass(cls):
        cls.relay.terminate();cls.relay.wait(timeout=5)

    def setUp(self):
        self.directory=tempfile.TemporaryDirectory()
        self.foreground=patch('sanctum_panel.game_is_foreground',return_value=False);self.foreground.start()
        self.app=App(self.directory.name,hotkeys=False)
        self.host=PartyClient();self.host_state=None
        self.host.start(self.url,'Host')
        self.until(lambda:self.host_state is not None)

    def tearDown(self):
        self.host.close();self.app.close();self.foreground.stop();self.directory.cleanup()

    def until(self,predicate):
        deadline=time.monotonic()+8
        while time.monotonic()<deadline:
            self.app.update();time.sleep(.02)
            while not self.host.events.empty():
                event=self.host.events.get_nowait()
                if 'state' in event:self.host_state=event['state']
                if event['type']=='error':self.fail(str(event))
            if predicate():return
        self.fail('Party navigation did not reach the expected state')

    def join(self,map_only=False):
        if map_only:self.app.sanctum.watch_action()
        else:self.app.begin_run(without_balance=True)
        party=self.app.party
        party.mode.set('custom');party.address.set(self.url);party.code.set(self.host_state['code']);party.connect(join=True)
        self.until(lambda:party.connected and party.state is not None)
        self.confirm(1,32,.85)

    def confirm(self,epoch,layout,score):
        self.host.publish(dict(type='update',epoch=epoch,evidence=dict(layout=layout,confidence=score)))
        self.until(lambda:self.app.sanctum.engine is not None and self.app.sanctum.engine.layout==layout and self.app.party.state['epoch']==epoch)

    def test_minimap_identified_before_join_is_shared_without_opening_M(self):
        panel=self.app.sanctum
        self.app.ledger.configure(capture_target='monitor');panel.watch_action()
        frame=hud(MapEngine(37).reference,(350,600))
        with patch('sanctum_panel.capture_image',return_value=frame),patch('sanctum_panel.capture_bounds',return_value=(0,0,1280,720)):
            for _ in range(3):
                panel.scan();self.until(lambda:not panel.busy);time.sleep(.4)
        self.assertTrue(panel.session.map_confirmed)
        party=self.app.party
        party.mode.set('custom');party.address.set(self.url);party.code.set(self.host_state['code']);party.connect(join=True)
        self.until(lambda:self.host_state['layout']==37)
        self.assertEqual(self.host_state['confidence'],.8)
        self.assertIsNone(self.app.ledger.active_start())

    def test_portuguese_join_applies_welcome_roster_and_shared_layout(self):
        self.app.set_language('pt-BR')
        self.app.fields['balance'].set('8217300')
        self.app.manual_start_button.invoke()
        self.assertEqual(self.app.ledger.active_start()['balance'],8217300)
        self.host.publish(dict(type='update',epoch=1,evidence=dict(layout=34,confidence=.8)))
        self.until(lambda:self.host_state['layout']==34)
        party=self.app.party
        party.mode.set('custom');party.address.set(self.url);party.code.set(self.host_state['code'])
        party.connect(join=True)
        self.until(lambda:len(self.host_state['members'])==2)
        self.until(lambda:party.connected and len(party.members.get_children())==2)
        self.until(lambda:self.app.sanctum.session.map_confirmed)
        self.assertEqual(self.app.sanctum.engine.layout,34)
        self.assertNotIn('Conectando',party.status.get())
        self.app.set_language('en')

    def test_portuguese_manual_balance_start_after_join_uses_shared_map(self):
        self.app.set_language('pt-BR')
        self.host.publish(dict(type='update',epoch=1,evidence=dict(layout=34,confidence=.8)))
        self.until(lambda:self.host_state['layout']==34)
        party=self.app.party
        party.mode.set('custom');party.address.set(self.url);party.code.set(self.host_state['code']);party.connect(join=True)
        self.until(lambda:party.connected)
        self.app.fields['balance'].set('8217300');self.app.manual_start_button.invoke()
        self.until(lambda:self.app.sanctum.session.map_confirmed)
        self.assertEqual(self.app.ledger.active_start()['balance'],8217300)
        self.assertEqual(self.app.sanctum.engine.layout,34)
        self.app.set_language('en')

    def test_join_recovers_after_a_transient_map_refresh_error(self):
        self.app.set_language('pt-BR')
        self.app.begin_run(without_balance=True)
        self.app.busy_capture=True
        attempts=[]
        def bounds(*args):
            attempts.append(True)
            if len(attempts)==1:raise OSError('Temporary window geometry failure')
            return (0,0,1280,720)
        with patch('sanctum_panel.game_is_foreground',return_value=True),patch('sanctum_panel.capture_bounds',side_effect=bounds):
            self.until(lambda:bool(attempts))
            party=self.app.party
            party.mode.set('custom');party.address.set(self.url);party.code.set(self.host_state['code']);party.connect(join=True)
            self.until(lambda:len(self.host_state['members'])==2)
            self.until(lambda:party.connected and len(party.members.get_children())==2)
        log=Path(self.directory.name)/'diagnostics/runtime.log'
        self.assertIn('Temporary window geometry failure',log.read_text(encoding='utf-8'))
        self.app.set_language('en')

    def test_party_explains_inactive_tracking_and_resumes_map_and_positions(self):
        baseline=self.app.ledger.summary()
        self.host.publish(dict(type='update',epoch=1,evidence=dict(layout=34,confidence=.8)))
        self.until(lambda:self.host_state['layout']==34)
        party=self.app.party;panel=self.app.sanctum
        party.mode.set('custom');party.address.set(self.url);party.code.set(self.host_state['code']);party.connect(join=True)
        self.until(lambda:party.connected and party.state['layout']==34)
        self.assertFalse(panel.session.watching)
        self.assertIn('Start map tracking',party.navigation_note.get())
        self.assertEqual(party.navigation_button.cget('text'),'Start map tracker')
        party.navigation_button.invoke()
        self.until(lambda:panel.session.map_confirmed and panel.engine.layout==34)
        self.assertIsNone(self.app.ledger.active_start())
        panel.end_watch()
        self.host.new_run(1,'Chaos');self.until(lambda:party.state['epoch']==2)
        self.host.publish(dict(type='update',epoch=2,evidence=dict(layout=34,confidence=.8)))
        self.until(lambda:party.state['layout']==34)
        self.assertFalse(panel.session.watching)
        self.assertFalse(panel.session.map_confirmed)
        self.assertIn('paused',party.navigation_note.get())
        self.assertEqual(party.navigation_button.cget('text'),'Resume map')
        self.app.set_language('pt-BR');self.app.update()
        self.assertEqual(party.navigation_button.cget('text'),'Retomar mapa')
        party.navigation_button.invoke()
        self.until(lambda:panel.session.map_confirmed and panel.engine.layout==34)
        self.host.publish(dict(type='update',epoch=2,layout=34,revision=party.state['revision'],position=[12,34]))
        self.until(lambda:bool(party.markers()))
        self.assertEqual(party.markers()[0]['position'],[12,34])
        panel.player=[56,78];panel.position_time=time.monotonic()
        self.until(lambda:next(m for m in self.host_state['members'] if m['id']==party.identity)['position']==[56,78])
        self.assertEqual(self.app.ledger.summary(),baseline)
        self.app.set_language('en')

    def test_warning_waits_for_new_run_and_confirmed_map_even_when_the_layout_repeats(self):
        self.join();self.app.fields['points'].set('192')
        active=self.app.ledger.active_start();baseline=self.app.ledger.summary()
        self.confirm(1,39,.96)
        self.assertEqual(self.app.party_notice.get(),'')
        self.host.new_run(1,'Chaos');self.until(lambda:self.app.party.state['epoch']==2)
        self.assertEqual(self.app.party_notice.get(),'')
        self.confirm(2,39,.85);self.until(lambda:bool(self.app.party_notice.get()))
        self.assertIn('unfinished',self.app.party_notice.get())
        self.assertEqual(self.app.ledger.active_start(),active)
        self.assertEqual(self.app.fields['points'].get(),'192')
        self.assertEqual(self.app.ledger.summary(),baseline)

    def test_warning_can_be_disabled_and_does_not_apply_to_map_only_sessions(self):
        self.join(map_only=True)
        self.host.new_run(1,'Chaos');self.until(lambda:self.app.party.state['epoch']==2)
        self.confirm(2,32,.85)
        self.assertEqual(self.app.party_notice.get(),'')
        self.assertEqual(self.app.overlay_run_status(),'')
        self.app.party.warn_unfinished.set(False);self.app.party.save_warning_preference()
        self.app.begin_run(without_balance=True);self.app.update()
        self.host.new_run(2,'Chaos');self.until(lambda:self.app.party.state['epoch']==3)
        self.confirm(3,39,.9)
        self.assertEqual(self.app.party_notice.get(),'')
        self.assertFalse(self.app.party.warn_unfinished.get())

    def test_finishing_an_old_ledger_run_then_catching_up_does_not_reset_the_party_again(self):
        self.join()
        self.host.new_run(1,'Chaos');self.until(lambda:self.app.party.state['epoch']==2)
        self.confirm(2,32,.85)
        self.app.fields['points'].set('190');self.assertTrue(self.app.save_run(quiet=True));self.app.update()
        self.app.begin_run(without_balance=True);self.app.update()
        self.until(lambda:self.app.party.state['layout']==32)
        self.assertEqual(self.app.party.state['epoch'],2)
        self.assertEqual(self.app.party_notice.get(),'')
        self.app.fields['points'].set('190');self.assertTrue(self.app.save_run(quiet=True));self.app.update()
        self.app.begin_run(without_balance=True)
        self.until(lambda:self.app.party.state['epoch']==3)
        self.assertEqual(self.app.party.state['started_by'],self.app.party.identity)
