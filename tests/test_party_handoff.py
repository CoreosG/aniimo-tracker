import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from party_handoff import save,consume


class PartyHandoffTests(unittest.TestCase):
    def test_handoff_is_encrypted_single_use_and_expires(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'party-update.bin'
            session=dict(id='a'*16,token='sensitive-test-token',code='ABCD2345',address='ws://127.0.0.1/party')
            with patch('party_handoff.time.time',return_value=100):save(path,session)
            self.assertNotIn(b'sensitive-test-token',path.read_bytes())
            with patch('party_handoff.time.time',return_value=110):restored=consume(path)
            self.assertEqual(restored['token'],session['token'])
            self.assertFalse(path.exists())
            self.assertIsNone(consume(path))
            with patch('party_handoff.time.time',return_value=100):save(path,session)
            with patch('party_handoff.time.time',return_value=161):self.assertIsNone(consume(path))
            self.assertFalse(path.exists())
            path.write_bytes(b'not a protected session')
            self.assertIsNone(consume(path))

