"""Downloaded maps live outside the public executable and user ledger."""
import os
from pathlib import Path
import shutil
import sys
from map_catalog import ALL_LAYOUTS,HIGH_TIER

BUNDLED=(Path(__file__).parent if getattr(sys,'frozen',False) else Path(__file__).resolve().parents[1])/'assets'
ASSETS=Path(os.environ['ANIIMO_MAP_ASSETS']) if os.environ.get('ANIIMO_MAP_ASSETS') else (
    Path(os.environ.get('LOCALAPPDATA',str(Path.home())))/'AniimoTracker'/'map-assets'
    if getattr(sys,'frozen',False) else BUNDLED)
if ASSETS!=BUNDLED:
    ASSETS.mkdir(parents=True,exist_ok=True)
    for name in ('blue.png','orange.png','orange-full.png','player.png','map-zoom-minus.png','map-zoom-plus.png','maps.json'):
        if not (ASSETS/name).exists():shutil.copyfile(BUNDLED/name,ASSETS/name)


def maps_ready():
    return all((ASSETS/'simulator'/f'{kind}-{layout}.json').is_file()
               for layout in ALL_LAYOUTS for kind in ('layout','route')) and all(
        (ASSETS/'simulator'/f'assets/lost-sanctum/maps/200{layout}-full.webp').is_file()
        for layout in ALL_LAYOUTS) and all((ASSETS/f'map-{layout}.webp').is_file() for layout in HIGH_TIER)
