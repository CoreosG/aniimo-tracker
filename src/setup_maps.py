"""Download the native map renderer's data; never execute upstream JavaScript."""
import argparse
import ast
import json
from pathlib import Path
import re
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen

from map_catalog import ALL_LAYOUTS, HIGH_TIER

SITE = 'https://aniimotools.dev'
PAGE = SITE + '/map/lost-sanctum/'


class DataModule:
    """Read only constant data literals, references and JSON.parse(string)."""
    number = r'-?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?'
    token = re.compile(r'''\s*("(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|''' + number + r'''|[A-Za-z_$][\w$]*|[{}\[\]:,;.!()=])''')

    def __init__(self, source):
        self.tokens = []
        pos = 0
        while pos < len(source.rstrip()):
            match = self.token.match(source, pos)
            if not match:
                raise ValueError('Unexpected syntax in upstream data module')
            self.tokens.append(match[1]); pos = match.end()
        self.pos = 0
        self.values = {}

    def take(self, expected=None):
        if self.pos >= len(self.tokens):
            raise ValueError('Incomplete upstream data module')
        value = self.tokens[self.pos]; self.pos += 1
        if expected is not None and value != expected:
            raise ValueError(f'Expected {expected}, found {value}')
        return value

    def peek(self):
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def value(self):
        token = self.take()
        if token == '{':
            result = {}
            while self.peek() != '}':
                key = self.take()
                key = ast.literal_eval(key) if key.startswith(('"', "'")) else key
                if self.peek() == ':':
                    self.take(':'); result[key] = self.value()
                else:
                    result[key] = self.values[key]
                if self.peek() != ',': break
                self.take(',')
            self.take('}'); return result
        if token == '[':
            result = []
            while self.peek() != ']':
                result.append(self.value())
                if self.peek() != ',': break
                self.take(',')
            self.take(']'); return result
        if token == 'JSON':
            self.take('.'); self.take('parse'); self.take('(')
            result = json.loads(self.value()); self.take(')'); return result
        if token.startswith(('"', "'")): return ast.literal_eval(token)
        if re.fullmatch(self.number, token): return float(token) if any(c in token for c in '.eE') else int(token)
        if token in ('true', 'false', 'null'): return json.loads(token)
        if token == '!':
            literal = self.take()
            if literal not in ('0', '1'): raise ValueError('Unsupported boolean')
            return literal == '0'
        if token in self.values: return self.values[token]
        raise ValueError(f'Unsupported data expression: {token}')

    def read(self):
        self.take('const')
        while True:
            name = self.take()
            self.take('=')
            self.values[name] = self.value()
            separator = self.take()
            if separator == ';': break
            if separator != ',': raise ValueError('Unsupported declaration')
        self.take('export'); self.take('{')
        default = None
        while self.peek() != '}':
            name = self.take(); alias = name
            if self.peek() == 'as': self.take('as'); alias = self.take()
            if alias == 'default': default = self.values[name]
            if self.peek() != ',': break
            self.take(',')
        self.take('}')
        if self.peek() == ';': self.take(';')
        if self.peek() is not None or not isinstance(default, dict):
            raise ValueError('Unsupported data module export')
        return default


def fetch(url):
    allowed = {'aniimotools.dev', 'aniimo.kr'}
    if urlsplit(url).scheme != 'https' or urlsplit(url).hostname not in allowed:
        raise ValueError('Unexpected asset host')
    request = Request(url, headers={'User-Agent': 'AniimoTracker/1.0 (local map setup)'})
    with urlopen(request, timeout=40) as response:
        if urlsplit(response.url).scheme != 'https' or urlsplit(response.url).hostname not in allowed:
            raise ValueError('Unexpected asset redirect')
        content = response.read(25_000_001)
    if len(content) > 25_000_000: raise ValueError('Asset exceeds download limit')
    return content


def save(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.download')
    temporary.write_bytes(content)
    temporary.replace(path)


def install(destination, progress=print):
    html = fetch(PAGE).decode('utf-8')
    match = re.search(r'src=["\']([^"\']*LostSanctumPage[^"\']*\.js)["\']', html)
    if not match: raise ValueError('AniimoTools page changed: planner module not found')
    planner_url = urljoin(PAGE, match[1])
    planner = fetch(planner_url).decode('utf-8')
    simulator = destination / 'simulator'
    for layout in ALL_LAYOUTS:
        modules = sorted(set(re.findall(r'["\'](?:\./)?(200' + str(layout) + r'\.[\w-]+\.js)["\']', planner)))
        if len(modules) != 2:
            raise ValueError(f'AniimoTools module format changed for layout {layout}')
        found = set()
        for module in modules:
            data = DataModule(fetch(urljoin(planner_url, module)).decode('utf-8')).read()
            kind = 'route' if 'pts' in data and 'D' in data else 'layout' if 'doors' in data and 'img' in data else None
            if kind is None or kind in found: raise ValueError('Unexpected upstream map data')
            found.add(kind)
            save(simulator / f'{kind}-{layout}.json', json.dumps(data).encode('utf-8'))
        image = fetch(SITE + f'/assets/lost-sanctum/maps/200{layout}-full.webp')
        save(simulator / f'assets/lost-sanctum/maps/200{layout}-full.webp', image)
        progress(f'Installed layout {layout}')
    # These unannotated references match the game floor texture used by SIFT.
    for layout in HIGH_TIER:
        save(destination / f'map-{layout}.webp', fetch(f'https://aniimo.kr/map/sanctums/sanctum_{layout}.webp'))
    save(simulator / 'SOURCE.txt', (
        'Locally downloaded map data and rendered maps from ' + PAGE + '\n'
        'Game floor references: https://aniimo.kr/en/palace-finder\n'
        'AniimoTools, MOANIIMO and the game owners retain their respective rights.\n'
        'Downloaded files are excluded from this Git repository.\n'
    ).encode('utf-8'))
    progress('Map pack ready. Open the game map to begin.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--assets-dir', type=Path, default=Path(__file__).resolve().parents[1]/'assets')
    args = parser.parse_args()
    try:
        install(args.assets_dir)
    except Exception as exc:
        parser.exit(1, f'Map setup failed: {exc}\nYour run history was not changed. Retry setup after checking the source site.\n')
