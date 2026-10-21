import io
import tempfile
import unittest
from pathlib import Path
from update_install import download_release,replace_release,asset_address,validate_release


class Response(io.BytesIO):
    def geturl(self):return 'https://release-assets.githubusercontent.com/github-production-release-asset/test'


class InstallTests(unittest.TestCase):
    def test_external_redirects_and_unverified_metadata_are_rejected(self):
        for address in ('https://example.com/AniimoTracker.exe','http://github.com/file','https://github.com.evil.test/file','https://user@github.com/file','https://github.com:8080/file'):
            with self.subTest(address=address),self.assertRaises(ValueError):asset_address(address)
        base=dict(version='0.3.2',download_url='https://github.com/CoreosG/aniimo-tracker/releases/download/v0.3.2/AniimoTracker.exe',sha256='a'*64,size=100)
        for change in (dict(sha256=''),dict(sha256='x'*64),dict(size=True),dict(size=999999999),dict(size=-1),dict(download_url='https://example.com/app.exe')):
            with self.subTest(change=change),self.assertRaises(ValueError):validate_release({**base,**change})

    def test_replacement_keeps_a_backup_and_rolls_back_if_relaunch_fails(self):
        digest='d20ddd75a42c4db549cd1fa807dd9fbaaa30d2c02391587a2ea6d27d2950795d'
        with tempfile.TemporaryDirectory() as directory:
            target=Path(directory)/'AniimoTracker.exe';target.write_bytes(b'old executable')
            candidate=Path(directory)/'pending.exe';candidate.write_bytes(b'MZtest')
            launched=[]
            backup=replace_release(candidate,target,digest,launched.append)
            self.assertEqual(launched,[target])
            self.assertEqual(target.read_bytes(),b'MZtest')
            self.assertEqual(backup.read_bytes(),b'old executable')
            target.write_bytes(b'current executable')
            def unavailable(path):raise OSError('launch refused')
            with self.assertRaises(OSError):replace_release(candidate,target,digest,unavailable)
            self.assertEqual(target.read_bytes(),b'current executable')
            self.assertFalse(target.with_name(target.name+'.new').exists())

    def test_download_is_bounded_and_verified_before_becoming_executable(self):
        payload=b'MZtest'
        info=dict(version='9.9.9',download_url='https://github.com/CoreosG/aniimo-tracker/releases/download/v9.9.9/AniimoTracker.exe',sha256='d20ddd75a42c4db549cd1fa807dd9fbaaa30d2c02391587a2ea6d27d2950795d',size=6)
        with tempfile.TemporaryDirectory() as directory:
            destination=Path(directory)/'update.exe'
            result=download_release(info,destination,opener=lambda *a,**k:Response(payload))
            self.assertEqual(result.read_bytes(),b'MZtest')
            destination.unlink()
            for content in (b'MZfail',b'MZtestoversize',b'MZ'):
                with self.subTest(content=content),self.assertRaises(ValueError):
                    download_release(info,destination,opener=lambda *a,**k:Response(content))
                self.assertFalse(destination.exists())
                self.assertFalse(destination.with_suffix('.download').exists())
