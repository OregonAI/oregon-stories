"""The fetch layer: every story's data comes from published, public artifacts, at
BUILD time, and a failed fetch FAILS THE BUILD.

The rule is OregonAI.github.io#1's, learned the hard way on the landing page: only a
404 may degrade (and the caller must handle it explicitly); every other failure raises,
the build exits nonzero, and the previously published page stays live on Pages. A story
rendered from partial data understates the platform and looks intentional.

Every fetch records (url, sha256) so each page's footer can cite the exact bytes its
numbers came from.
"""
from __future__ import annotations

import hashlib
import urllib.error
import urllib.request

RAW = "https://raw.githubusercontent.com/OregonAI"
PAGES = "https://oregonai.github.io"

FETCHED: list[dict] = []   # [{"label", "url", "sha256"}] in fetch order


class FetchError(RuntimeError):
    pass


def fetch(url: str, label: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "oregon-stories-builder"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            body = r.read()
    except urllib.error.HTTPError as e:
        raise FetchError(f"{label}: {url} answered HTTP {e.code}") from e
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise FetchError(f"{label}: {url}: {e}") from e
    FETCHED.append({"label": label, "url": url,
                    "sha256": hashlib.sha256(body).hexdigest()})
    return body


def sources_for_footer() -> list[dict]:
    return list(FETCHED)
