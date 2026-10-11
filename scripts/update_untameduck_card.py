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
        "background": "#FFFFFF",
        "border": "#E7E7E7",
        "heading": "#161616",
        "text": "#262626",
        "muted": "#666666",
        "separator": "#E8E8E8"
    },
    "dark": {
        "background": "#000000",
        "border": "#2A2A2A",
        "heading": "#FFFFFF",
        "text": "#FFFFFF",
        "muted": "#A0A0A0",
        "separator": "#262626"
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
    """Wide, half-height 960x122 card with monochrome light/dark backgrounds."""
    c = THEMES[theme]
    ff = "-apple-system,BlinkMacSystemFont,Segoe UI,Arial,sans-serif"
    items = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="960" height="122" viewBox="0 0 960 122" role="img" aria-labelledby="title desc">',
        f'<title id="title">Project Hub / UntameDuck — {theme} theme</title>',
        '<desc id="desc">UntameDuck GitHub organization statistics: public repositories, contributors, stars and forks</desc>',
        f'<rect x="0.75" y="0.75" width="958.5" height="120.5" rx="13.25" fill="{c["background"]}" stroke="{c["border"]}" stroke-width="1.5"/>',
        f'<text x="32" y="70" font-family="{ff}" font-size="24" fill="{c["heading"]}">Project Hub / <tspan font-weight="700">UntameDuck</tspan></text>',
        f'<path d="M428 31V92" fill="none" stroke="{c["separator"]}" stroke-width="1"/>',
    ]
    positions = (460, 589, 710, 832)
    for (label, value), x in zip(stats, positions):
        items.append(
            f'<text x="{x}" y="59" font-family="{ff}" font-size="27" font-weight="700" fill="{c["text"]}">{value:,}</text>'
        )
        items.append(
            f'<text x="{x}" y="80" font-family="{ff}" font-size="10" letter-spacing=".45" fill="{c["muted"]}">{label}</text>'
        )
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
