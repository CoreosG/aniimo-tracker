"""Small, versioned party messages. No images, accounts or ledger data."""
import math
from urllib.parse import urlsplit, urlunsplit

DEFAULT_SERVER = 'wss://eggheist.banneret.app/party'
COLORS = ('#3df5ff', '#ff82cb', '#a6fa65')
VERSION = 1


def server_url(value):
    value = value.strip()
    if '://' not in value: value = 'wss://' + value
    parsed = urlsplit(value)
    if parsed.scheme in ('http', 'https'):
        parsed = parsed._replace(scheme={'http': 'ws', 'https': 'wss'}[parsed.scheme])
    if (parsed.scheme not in ('ws', 'wss') or not parsed.hostname or parsed.username or
            parsed.password or parsed.query or parsed.fragment):
        raise ValueError('Use a server address such as wss://eggheist.banneret.app/party')
    return urlunsplit(parsed._replace(path=parsed.path.rstrip('/') or '/party'))


def username(value):
    if not isinstance(value, str): raise ValueError('Enter a username (1–24 characters).')
    value = value.strip()
    if not 1 <= len(value) <= 24 or not value.isprintable():
        raise ValueError('Enter a username (1–24 characters).')
    return value


def evidence_score(reading):
    if not reading.get('map_screen') or len(reading.get('candidates', [])) != 1: return 0.
    scores = reading.get('scores', {})
    values = [scores.get(kind, 0.) for kind in ('orange', 'blue')]
    if any(type(n) not in (int, float) or not math.isfinite(n) for n in values): return 0.
    return round(max(0., min(1., min(values)) - .03 * len(reading.get('occluded_portals', []))), 3)
