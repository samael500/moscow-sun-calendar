"""Render the versioned 1200×630 card with the actual local blog fonts."""
import argparse
import hashlib
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from functools import partial
from pathlib import Path
import re
from threading import Thread
from tempfile import TemporaryDirectory
from PIL import Image
from playwright.sync_api import sync_playwright
ROOT = Path(__file__).resolve().parents[1]


def build(executable=None):
    server = ThreadingHTTPServer(('127.0.0.1', 0), partial(SimpleHTTPRequestHandler, directory=ROOT))
    Thread(target=server.serve_forever, daemon=True).start()
    try:
        with TemporaryDirectory() as temp, sync_playwright() as p:
            browser = p.chromium.launch(**({'executable_path': executable} if executable else {}))
            page = browser.new_page(viewport={'width': 1200, 'height': 630}, device_scale_factor=1)
            page.goto(f'http://127.0.0.1:{server.server_port}/design/social.html', wait_until='networkidle')
            assert page.evaluate('''async () => {
              const a = await document.fonts.load('500 66px Literata', 'У каждого города своё солнце');
              const b = await document.fonts.load('400 30px "PT Sans"', 'Бродов нет');
              await document.fonts.ready;
              return a.length > 0 && b.length > 0 && [...a, ...b].every(face => face.status === 'loaded');
            }'''), 'Local fonts did not load'
            target = Path(temp) / 'card.png'
            page.screenshot(path=str(target))
            browser.close()
            raw = target.read_bytes()
            with Image.open(target) as card:
                assert card.size == (1200, 630)
                name = 'social-' + hashlib.sha256(raw).hexdigest()[:12] + '.png'
                (ROOT / 'web' / name).write_bytes(raw)
            index = ROOT / 'web/index.html'
            html = re.sub(r'https://brodov.net/sun-calendar/social(?:-[a-f0-9]+)?\.png', 'https://brodov.net/sun-calendar/' + name, index.read_text())
            html = html.replace('name="twitter:card" content="summary"', 'name="twitter:card" content="summary_large_image"')
            if 'og:image:width' not in html:
                html = html.replace('<link rel="stylesheet"', '<meta property="og:image:width" content="1200"><meta property="og:image:height" content="630"><meta property="og:image:alt" content="У каждого города своё солнце. Календарь восходов и закатов — Бродов нет."><meta name="twitter:image:alt" content="У каждого города своё солнце. Календарь восходов и закатов — Бродов нет.">\n<link rel="stylesheet"')
            index.write_text(html)
            print(name)
    finally:
        server.shutdown(); server.server_close()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--browser', help='Optional Chromium executable path')
    build(parser.parse_args().browser)
