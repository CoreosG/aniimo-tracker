"""Untrusted relay traffic is exercised over loopback, without a real account."""
import json
import queue
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from websockets.sync.server import serve
from app import App
from party_client import PartyClient, read_state, updated_state


IDENTITY = '0123456789abcdef'


def state():
    return dict(code='ABCDEFGH', difficulty='Chaos', epoch=1, revision=0, layout=None,
                confidence=0., source=None, host=IDENTITY, started_by=None,
                members=[dict(id=IDENTITY, username='Player', color='#3df5ff', online=True,
                              position=None, age=None)])


def welcome(snapshot):
    return dict(type='welcome', version=1, id=IDENTITY, token='a'*43, state=snapshot)


class MaliciousRelay:
    def __init__(self, reply, following=()):
        self.reply, self.following = reply, following

    def __enter__(self):
        def handler(socket):
            try:
                socket.recv(timeout=5)
                socket.send(json.dumps(self.reply))
                for reply in self.following:
                    socket.send(json.dumps(reply))
                socket.recv(timeout=5)
            except Exception:
                pass
        self.server = serve(handler, '127.0.0.1', 0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f'ws://127.0.0.1:{self.server.socket.getsockname()[1]}/party'
        return self

    def __exit__(self, *args):
        self.server.shutdown()
        self.thread.join(timeout=3)


class UntrustedPartyTests(unittest.TestCase):
    def test_malformed_welcome_cannot_break_tk_party_polling_or_change_the_ledger(self):
        malformed = state()
        del malformed['members'][0]['online']
        with MaliciousRelay(welcome(malformed)) as relay, tempfile.TemporaryDirectory() as directory, \
                patch('sanctum_panel.game_is_foreground', return_value=False):
            app = App(directory, hotkeys=False)
            try:
                baseline = app.ledger.summary()
                app.party.connecting = True
                app.party.client.start(relay.url, 'Player')
                deadline = time.monotonic()+3
                while app.party.client.events.empty() and time.monotonic()<deadline:
                    time.sleep(.01)
                self.assertFalse(app.party.client.events.empty())
                app.party.tick()
                self.assertIsNone(app.party.state)
                self.assertEqual(app.ledger.summary(), baseline)
            finally:
                app.close()

    def test_untrusted_error_objects_cannot_reach_ui_dictionary_lookups(self):
        with MaliciousRelay(dict(type='error', code=[])) as relay:
            client = PartyClient()
            try:
                client.start(relay.url, 'Player')
                event = client.events.get(timeout=2)
                self.assertEqual(event, dict(type='reconnecting'))
            finally:
                client.close()

    def test_full_state_projection_rejects_bad_presence_identity_and_evidence(self):
        cases = []
        for key, value in [('host', []), ('host', 'f'*16), ('source', 'https://evil.invalid'),
                           ('started_by', {}), ('confidence', float('nan')), ('epoch', True),
                           ('members', {}), ('members', [])]:
            snapshot = state();snapshot[key] = value;cases.append(snapshot)
        for key, value in [('online', []), ('age', 'old'), ('position', [float('inf'), 50]),
                           ('id', ['0123456789abcdef']), ('username', 'x'*25)]:
            snapshot = state();snapshot['members'][0][key] = value;cases.append(snapshot)
        duplicate = state();duplicate['members'] *= 2;cases.append(duplicate)
        for number, snapshot in enumerate(cases):
            with self.subTest(case=number), self.assertRaises(ValueError):
                read_state(snapshot)

    def test_known_fields_only_and_legacy_starter_preserve_navigation(self):
        snapshot = state();del snapshot['started_by']
        snapshot['download_url'] = 'https://evil.invalid/payload.exe'
        snapshot['members'][0]['command'] = 'calc.exe'
        parsed = read_state(snapshot)
        self.assertNotIn('download_url', parsed)
        self.assertNotIn('command', parsed['members'][0])
        self.assertIsNone(parsed['started_by'])
        # Historical evidence IDs can belong to a member who has since left.
        snapshot.update(layout=32, revision=1, confidence=.9, source='f'*16, started_by='e'*16)
        self.assertEqual(read_state(snapshot)['layout'], 32)

    def test_position_delta_rejects_malformed_unknown_and_duplicate_members(self):
        snapshot = state();snapshot.update(layout=32, revision=1, confidence=.9, source=IDENTITY)
        for positions in ([[[IDENTITY], [1, 2], 0]], [['f'*16, [1, 2], 0]],
                          [[IDENTITY, [1, 2], 0]]*2, [[IDENTITY, [1, 2]]],
                          [[IDENTITY, [float('nan'), 2], 0]], [[IDENTITY, None, {}]]):
            with self.subTest(positions=positions), self.assertRaises(ValueError):
                updated_state(snapshot, dict(type='positions', epoch=1, revision=1, positions=positions))

    def test_incoming_state_flood_disconnects_before_it_can_keep_refilling_the_ui_queue(self):
        messages = [dict(type='state', state=state())]*1000
        with MaliciousRelay(welcome(state()), messages) as relay:
            client = PartyClient()
            try:
                client.start(relay.url, 'Player')
                deadline = time.monotonic()+3
                reconnecting = False
                while time.monotonic()<deadline:
                    try:event = client.events.get(timeout=.5)
                    except queue.Empty:continue
                    if event['type'] == 'reconnecting':
                        reconnecting = True;break
                self.assertTrue(reconnecting, 'A relay flood must be stopped in the background')
                self.assertLessEqual(client.events.qsize(), 8)
            finally:
                client.close()
