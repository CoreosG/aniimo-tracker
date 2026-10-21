import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image
from map_catalog import ALL_LAYOUTS
from setup_maps import install_recognition


class MapUpgradeTests(unittest.TestCase):
    def test_upgrade_preserves_existing_maps_and_adds_every_difficulty_and_outdoor_reference(self):
        image=io.BytesIO();Image.new('RGB',(32,32),(100,100,100)).save(image,format='WEBP')
        with tempfile.TemporaryDirectory() as folder,patch('setup_maps.fetch',return_value=image.getvalue()):
            path=Path(folder)
            old=b'existing-reference';(path/'map-32.webp').write_bytes(old)
            install_recognition(path,progress=lambda message:None)
            self.assertEqual((path/'map-32.webp').read_bytes(),old)
            self.assertEqual((path/'outdoor-minimap.webp').read_bytes(),image.getvalue())
            self.assertTrue(all((path/f'map-{layout}.webp').is_file() for layout in ALL_LAYOUTS))
