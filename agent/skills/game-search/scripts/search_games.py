#!/usr/bin/env python3
"""Find candidate game detail pages using the HTML index from the Hermes skill."""
import argparse
from html.parser import HTMLParser
import json
import re
import sys
from urllib.parse import urlencode, urljoin, urlsplit
from urllib.request import Request, urlopen

INDEX = "https://www.torrentdownloads.pro"


class Results(HTMLParser):
    def __init__(self):
        super().__init__()
        self.items = {}
        self.link = None
        self.words = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            url = urljoin(INDEX, dict(attrs).get("href") or "")
            parts = urlsplit(url)
            self.link = url if (parts.scheme == "https" and parts.netloc == urlsplit(INDEX).netloc
                                and not parts.fragment and not parts.query
                                and re.fullmatch(r"/torrent/\d+/[^/?#]+/?", parts.path)) else None
            self.words = []

    def handle_data(self, data):
        if self.link:
            self.words.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self.link:
            title = " ".join("".join(self.words).split())
            if title:
                self.items.setdefault(self.link, title)
            self.link = None


def fetch(url):
    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(req, timeout=20) as response:
        if urlsplit(response.geturl()).hostname != urlsplit(INDEX).hostname:
            raise ValueError("Indexer redirected to another host")
        raw = response.read(4_000_001)
        if len(raw) > 4_000_000:
            raise ValueError("Search response exceeded 4 MB")
        return raw.decode(response.headers.get_content_charset() or "utf-8", errors="replace")


class Detail(HTMLParser):
    def __init__(self):
        super().__init__()
        self.text = []
        self.hidden = False

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.hidden = True

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.hidden = False

    def handle_data(self, data):
        if not self.hidden:
            self.text.append(data)

    def fields(self):
        text = " ".join(" ".join(self.text).split())
        out = {}
        for key, pattern in [
            ("infohash", r"\bInfohash:\s*([a-f0-9]{40})\b"),
            ("size", r"\bTotal Size:\s*([\d.,]+\s*[KMGT]i?B)\b"),
            ("seeds", r"\bSeeds:\s*([\d,]+)"),
        ]:
            m = re.search(pattern, text, re.I)
            if m:
                out[key] = m.group(1)
        return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("title")
    parser.add_argument("--platform", default="")
    parser.add_argument("--details", type=int, choices=range(0, 11), default=0, metavar="0..10",
                        help="Read metadata for up to this many candidates")
    args = parser.parse_args()
    query = " ".join(filter(None, [args.title.strip(), args.platform.strip()]))
    if not args.title.strip():
        parser.error("Enter a game title")
    url = INDEX + "/search/?" + urlencode({"search": query})
    page = fetch(url)
    result = Results()
    result.feed(page)
    result.close()
    if not result.items:
        print("No detail links parsed. Check the query or inspect the search page for availability or layout changes.", file=sys.stderr)
    candidates = [{"title": title, "detail_url": url} for url, title in result.items.items()]
    for item in candidates[:args.details]:
        try:
            detail = Detail()
            detail.feed(fetch(item["detail_url"]))
            detail.close()
            item.update(detail.fields())
        except (OSError, ValueError) as exc:
            item["detail_error"] = str(exc)
    print(json.dumps(candidates, indent=2))


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError) as exc:
        sys.exit(f"Search failed: {exc}")
