"""See the five layouts before choosing one — in a browser, on this machine only.

Choosing a layout from five prose descriptions is guessing. This renders all
five with the user's own CV in them and opens them side by side, so the choice
is made by looking.

The page holds an entire career history, so the server is deliberately small and
deliberately closed:

  * it binds to **127.0.0.1** and nothing else, so it is unreachable from the
    network even on a shared or hostile wifi;
  * it takes an **ephemeral port** (0), so nothing is predictable enough to be
    waiting for it;
  * every URL carries a **random token** minted per run, so another process on
    the same machine cannot guess the address of the page;
  * it is a **daemon thread** and serves prepared strings from memory — it reads
    no files, accepts no input, and dies with the process rather than outliving
    the conversation that started it.

It is a preview, not a service. If it feels like it should have a login, that is
the signal it should not exist at all.
"""

from __future__ import annotations

import secrets
import sys
import threading
import webbrowser
from dataclasses import dataclass
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .document import CvDocument
from .templates import TEMPLATES, render_html

LOOPBACK = "127.0.0.1"


def _index(token: str, pages: dict[str, str]) -> str:
    """One page listing every layout, each in its own frame at page proportions."""
    cards = "\n".join(
        f"""
      <figure>
        <figcaption>
          <strong>{TEMPLATES[layout_id].name}</strong>
          <span class="{'safe' if TEMPLATES[layout_id].ats_safe else 'human'}">{
              'portal-safe' if TEMPLATES[layout_id].ats_safe else 'send to a person'
          }</span>
          <p>{TEMPLATES[layout_id].blurb}</p>
          <a href="/{token}/{layout_id}" target="_blank">open full size &rarr;</a>
        </figcaption>
        <div class="sheet"><iframe src="/{token}/{layout_id}" title="{
            TEMPLATES[layout_id].name
        }" loading="lazy"></iframe></div>
      </figure>"""
        for layout_id in pages
    )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>cv-tailor layouts</title>
<style>
  :root {{ color-scheme: light; }}
  body {{
    margin: 0; padding: 28px 24px 60px;
    background: #f2f1ee; color: #1b1d1e;
    font: 15px/1.5 "Segoe UI", system-ui, sans-serif;
  }}
  h1 {{ font-size: 20px; margin: 0 0 4px; }}
  .lede {{ margin: 0 0 24px; color: #55585a; max-width: 66ch; }}
  .grid {{ display: grid; gap: 26px; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); }}
  figure {{ margin: 0; }}
  figcaption {{ margin-bottom: 8px; }}
  figcaption p {{ margin: 4px 0 6px; color: #55585a; font-size: 13px; }}
  figcaption span {{
    font-size: 11px; letter-spacing: .04em; padding: 2px 7px; border-radius: 999px;
    margin-left: 6px; vertical-align: 2px;
  }}
  .safe {{ background: #dceadd; color: #1f5130; }}
  .human {{ background: #efe0cd; color: #7a4a16; }}
  a {{ color: #7a2e2e; }}
  .sheet {{
    aspect-ratio: 210 / 297; background: #fff; overflow: hidden;
    box-shadow: 0 1px 2px rgba(0,0,0,.14), 0 8px 24px rgba(0,0,0,.10);
  }}
  iframe {{
    width: 794px; height: 1123px; border: 0;
    transform: scale(var(--s, .48)); transform-origin: 0 0;
  }}
</style></head>
<body>
  <h1>Your CV in five layouts</h1>
  <p class="lede">Portal-safe layouts are single column with no sidebar, icons or
  images, because parsing is the only hard gate on an application. The other two
  look better by doing what a parser mishandles &mdash; send those to a person
  directly. Tell your assistant which you want.</p>
  <div class="grid">{cards}</div>
  <script>
    // The frame is a fixed A4 in pixels; scale it to whatever width the card got.
    const fit = () => document.querySelectorAll('.sheet').forEach(s => {{
      s.querySelector('iframe').style.setProperty('--s', s.clientWidth / 794);
    }});
    addEventListener('resize', fit); fit();
  </script>
</body></html>"""


class _Handler(BaseHTTPRequestHandler):
    """Serves prepared strings and nothing else. No filesystem, no parameters."""

    def __init__(self, *args, pages: dict[str, str], **kwargs) -> None:
        self._pages = pages
        super().__init__(*args, **kwargs)

    def do_GET(self) -> None:
        body = self._pages.get(self.path)
        if body is None:
            # Same answer for a wrong token and a wrong path, so neither can be
            # probed for by the difference between the replies.
            self.send_error(404)
            return
        encoded = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        # The page holds a career history; keep it out of anything embedding it.
        self.send_header("X-Frame-Options", "SAMEORIGIN")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, *args) -> None:
        """Silence. This shares stdout with an MCP server's JSON-RPC stream."""


@dataclass
class Preview:
    url: str
    port: int
    layouts: list[str]
    _server: ThreadingHTTPServer

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()


def start_preview(document: CvDocument, *, open_browser: bool = True) -> Preview:
    """Render every layout and serve them on loopback. Returns the URL to open."""
    token = secrets.token_urlsafe(16)
    pages = {
        f"/{token}/{layout_id}": render_html(document, template)
        for layout_id, template in TEMPLATES.items()
    }
    pages[f"/{token}"] = _index(token, {k.rsplit("/", 1)[1]: v for k, v in pages.items()})
    pages[f"/{token}/"] = pages[f"/{token}"]

    server = ThreadingHTTPServer((LOOPBACK, 0), partial(_Handler, pages=pages))
    # Daemon: the preview must never be the reason a session refuses to exit.
    threading.Thread(target=server.serve_forever, daemon=True, name="cv-tailor-preview").start()

    port = server.server_address[1]
    url = f"http://{LOOPBACK}:{port}/{token}"
    if open_browser:
        # Best effort. A headless machine has no browser and that is not an error;
        # the URL is returned either way.
        try:
            webbrowser.open(url)
        except Exception as exc:
            # stderr, never stdout: this process speaks JSON-RPC on stdout, and a
            # stray print there breaks the protocol outright.
            #
            # And WITHOUT the url. It carries the session token gating a page that
            # holds a whole career history, and a host captures this stream into a
            # log file — which outlives the conversation the url was returned in,
            # and has different permissions. The caller already has the url.
            print(f"could not open a browser ({exc}); the preview url was returned "
                  "to you and still works", file=sys.stderr)
    return Preview(url=url, port=port, layouts=list(TEMPLATES), _server=server)


__all__ = ["LOOPBACK", "Preview", "start_preview"]
