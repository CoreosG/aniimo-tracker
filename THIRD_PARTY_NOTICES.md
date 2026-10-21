# Third-party notices

The tracker implements its own native UI, ledger, forecasts, analytics,
screen-recognition logic and overlay. Its optional map installation uses data
and visual references provided by the following projects:

| Source | Local files | Use |
| --- | --- | --- |
| [AniimoTools](https://aniimotools.dev/map/lost-sanctum/) | `assets/simulator/layout-*.json`, `route-*.json`, `assets/lost-sanctum/maps/*.webp` | Layout metadata, room positions, routing graph and rendered floor plans |
| [MOANIIMO](https://aniimo.kr/en/palace-finder) | `assets/map-*.webp`; alignment coordinates in `assets/maps.json` | Floor texture references and portal alignment |
| Aniimo, Pawprint Studio / FunPlus | Small `.png` marker crops in `assets/` | Recognizing the game UI and player marker |

Downloaded map files and any separately installed website mirror are ignored by
Git and are not hosted in this repository. Run `setup_maps.py` to acquire the
map files directly from their source sites. This project does not claim
ownership of them or grant redistribution rights. The optional original
simulator remains credited to AniimoTools.

Game names, artwork and trademarks belong to their respective owners. The
small recognition crops contain only UI markers, without player identifiers.

Runtime libraries are listed in `requirements.txt`. Their licenses and any
binary-distribution notices must be preserved when packaging the application.
