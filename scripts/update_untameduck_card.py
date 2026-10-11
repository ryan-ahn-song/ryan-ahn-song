#!/usr/bin/env python3
"""Render a compact, responsive-light/dark UntameDuck organization card.

This script reads only public GitHub organization repository data. No personal
access token or modification to any UntameDuck repository is required.
"""
import json
import os
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, quote
from urllib.request import Request, urlopen

ORG = "UntameDuck"
OUT = Path(__file__).resolve().parents[1] / "assets"
API_ROOT = "https://api.github.com"
THEMES = {
    "light": {
        "bg1": "#F8FDFF", "bg2": "#E9F7FC", "stroke": "#CCE9F3",
        "heading": "#123E58", "text": "#266480", "muted": "#628B9E",
        "accent": "#179AC0", "glow": "#BFEAF6", "divider": "#C2DEE8",
        "badge": "#E1F5FB", "badge_text": "#147B9D",
        "wave": "#8ED5EA"
    },
    "dark": {
        "bg1": "#101D2B", "bg2": "#102D3D", "stroke": "#2D5368",
        "heading": "#F0FAFF", "text": "#CFEDF7", "muted": "#91B6C5",
        "accent": "#71D6EB", "glow": "#22617B", "divider": "#31536A",
        "badge": "#173D50", "badge_text": "#82E1F2",
        "wave": "#31A4C8"
    }
}


def github(path, params=None, allow_empty=False):
    query = ("?" + urlencode(params)) if params else ""
    url = API_ROOT + path + query
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "ryan-ahn-song-org-profile-card",
    }
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = "Bearer " + token

    for attempt in range(5):
        try:
            with urlopen(Request(url, headers=headers), timeout=40) as response:
                if response.status == 202:
                    if attempt < 4:
                        time.sleep(5 * (attempt + 1))
                        continue
                    raise RuntimeError("Contributor data is still being calculated")
                payload = response.read()
                return json.loads(payload) if payload else []
        except HTTPError as exc:
            if allow_empty and exc.code in (404, 409):
                return []
            if exc.code in (500, 502, 503, 504) and attempt < 4:
                time.sleep(4 * (attempt + 1))
                continue
            raise RuntimeError(f"GitHub API returned {exc.code} for {url}") from exc
        except (URLError, TimeoutError) as exc:
            if attempt < 4:
                time.sleep(4 * (attempt + 1))
                continue
            raise RuntimeError(f"Could not retrieve {url}") from exc
    raise RuntimeError("Exceeded retries: " + url)


def pages(path, params=None, allow_empty=False):
    for page in range(1, 51):
        data = github(path, {**(params or {}), "per_page": 100, "page": page}, allow_empty)
        if not isinstance(data, list):
            raise RuntimeError("Unexpected response for " + path)
        yield from data
        if len(data) < 100:
            return
    raise RuntimeError("Pagination limit reached at " + path)


def collect_stats():
    repos = [
        r for r in pages(f"/orgs/{ORG}/repos", {"type": "public"})
        if not r.get("private")
    ]
    contributors = set()
    stars = 0
    forks = 0

    for repo in repos:
        stars += int(repo.get("stargazers_count", 0) or 0)
        forks += int(repo.get("forks_count", 0) or 0)
        if repo.get("size", 0) == 0:
            continue

        path = f"/repos/{quote(ORG)}/{quote(repo['name'])}/contributors"
        for person in pages(path, {"anon": "false"}, allow_empty=True):
            login = person.get("login", "")
            if not login or person.get("type") == "Bot" or login.lower().endswith("[bot]"):
                continue
            contributors.add(login.casefold())

    return [
        ("REPOSITORIES", len(repos)),
        ("CONTRIBUTORS", len(contributors)),
        ("STARS", stars),
        ("FORKS", forks),
    ]


def svg(stats, theme):
    c = THEMES[theme]
    ff = "-apple-system,BlinkMacSystemFont,Segoe UI,Arial,sans-serif"
    items = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="960" height="244" viewBox="0 0 960 244" role="img" aria-labelledby="title desc">',
        f'<title id="title">UntameDuck organization — {theme} theme</title>',
        '<desc id="desc">Live public GitHub organization repository statistics</desc>',
        '<defs>',
        f'  <linearGradient id="background" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{c["bg1"]}"/><stop offset="1" stop-color="{c["bg2"]}"/></linearGradient>',
        f'  <radialGradient id="ambient"><stop offset="0" stop-color="{c["glow"]}" stop-opacity=".75"/><stop offset="1" stop-color="{c["glow"]}" stop-opacity="0"/></radialGradient>',
        '  <clipPath id="card-clip"><rect x="1" y="1" width="958" height="242" rx="19"/></clipPath>',
        '</defs>',
        f'<rect x="1" y="1" width="958" height="242" rx="19" fill="url(#background)" stroke="{c["stroke"]}" stroke-width="1.5"/>',
        '<g clip-path="url(#card-clip)">',
        '<ellipse cx="862" cy="5" rx="210" ry="140" fill="url(#ambient)" opacity=".5"/>',
        f'<path d="M692 117C759 66 814 150 968 73" fill="none" stroke="{c["wave"]}" stroke-width="2" opacity=".24"/>',
        f'<path d="M712 133C788 90 856 173 990 110" fill="none" stroke="{c["wave"]}" stroke-width="2" opacity=".16"/>',
        '</g>',
        f'<rect x="40" y="34" width="47" height="47" rx="13" fill="{c["badge"]}"/>',
        f'<path d="M50 55c7-7 13 7 20 0s9-3 10 0M50 66c7-7 13 7 20 0s9-3 10 0" fill="none" stroke="{c["badge_text"]}" stroke-width="2.5" stroke-linecap="round"/>',
        f'<text x="102" y="57" font-family="{ff}" font-size="26" font-weight="700" fill="{c["heading"]}">UntameDuck</text>',
        f'<text x="103" y="79" font-family="{ff}" font-size="13" fill="{c["muted"]}">Building software together.</text>',
        f'<text x="763" y="52" font-family="{ff}" font-size="11.5" letter-spacing=".7" font-weight="600" fill="{c["accent"]}">EXPLORE ORGANIZATION  &#8599;</text>',
        f'<path d="M41 115H919" fill="none" stroke="{c["divider"]}" stroke-width="1"/>',
    ]
    xs = [46, 271, 496, 721]
    for i, ((label, value), x) in enumerate(zip(stats, xs)):
        if i:
            items.append(f'<path d="M{x-15} 144V207" fill="none" stroke="{c["divider"]}" stroke-width="1"/>')
        items.append(f'<text x="{x}" y="177" font-family="{ff}" font-weight="700" font-size="30" fill="{c["heading"]}">{value:,}</text>')
        items.append(f'<text x="{x+1}" y="202" font-family="{ff}" letter-spacing=".8" font-size="11" fill="{c["muted"]}">{label}</text>')
    items.append('</svg>')
    return "\n".join(items) + "\n"


def main():
    stats = collect_stats()
    OUT.mkdir(parents=True, exist_ok=True)
    for theme in THEMES:
        dest = OUT / f"untameduck-{theme}.svg"
        output = svg(stats, theme)
        if not dest.exists() or dest.read_text(encoding="utf-8") != output:
            dest.write_text(output, encoding="utf-8")
    print("UntameDuck organization metrics:", ", ".join(f"{k}: {v}" for k, v in stats))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Card generation failed: {exc}", file=sys.stderr)
        sys.exit(1)
