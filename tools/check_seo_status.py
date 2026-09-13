# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import re
import sys
import time
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen


DEFAULT_PATHS = [
    "/",
    "/robots.txt",
    "/sitemap.xml",

    "/bus-rental",
    "/schulen",
    "/fuhrpark",
    "/anfrage",
    "/aktuelles",
    "/kontakt",
    "/impressum",
    "/datenschutz",
    "/agb",

    "/bus-mieten-wien",
    "/reisebus-mieten-wien",
    "/schulfahrten-wien",
    "/schulausflug-wien",
    "/kindertransport-wien",
    "/gruppentransfer-wien",
    "/firmenausflug-bus-wien",
    "/vereinsausflug-bus-wien",
    "/tagesausflug-bus-wien",
    "/transportservice-wien",
    "/busunternehmen-wien",
]


EXPECTED_SITEMAP_PATHS = [
    "/",
    "/bus-rental",
    "/schulen",
    "/fuhrpark",
    "/anfrage",
    "/aktuelles",
    "/kontakt",
    "/impressum",
    "/datenschutz",
    "/agb",

    "/bus-mieten-wien",
    "/reisebus-mieten-wien",
    "/schulfahrten-wien",
    "/schulausflug-wien",
    "/kindertransport-wien",
    "/gruppentransfer-wien",
    "/firmenausflug-bus-wien",
    "/vereinsausflug-bus-wien",
    "/tagesausflug-bus-wien",
    "/transportservice-wien",
    "/busunternehmen-wien",
]


@dataclass
class FetchResult:
    path: str
    url: str
    status: int | None
    final_url: str | None
    content_type: str
    body: str
    error: str | None
    elapsed_ms: int


class HeadParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title = ""
        self._in_title = False
        self.meta_robots = []
        self.canonicals = []
        self.meta_descriptions = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        tag = tag.lower()

        if tag == "title":
            self._in_title = True

        if tag == "meta":
            name = (attrs.get("name") or "").lower()
            if name == "robots":
                self.meta_robots.append(attrs.get("content", ""))
            if name == "description":
                self.meta_descriptions.append(attrs.get("content", ""))

        if tag == "link":
            rel = (attrs.get("rel") or "").lower()
            if rel == "canonical" and attrs.get("href"):
                self.canonicals.append(attrs["href"])

    def handle_endtag(self, tag):
        if tag.lower() == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._in_title:
            self.title += data.strip()


def normalize_base_url(base_url: str) -> str:
    base_url = base_url.strip()
    if not base_url.startswith(("http://", "https://")):
        base_url = "https://" + base_url
    return base_url.rstrip("/") + "/"


def fetch(base_url: str, path: str, timeout: int = 25) -> FetchResult:
    url = urljoin(base_url, path.lstrip("/"))
    started = time.perf_counter()
    req = Request(
        url,
        headers={
            "User-Agent": "AustriaExpressSEOChecker/1.0 (+https://austria-express.eu)",
            "Accept": "text/html,application/xml,text/xml,text/plain,*/*",
        },
    )

    try:
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            charset = resp.headers.get_content_charset() or "utf-8"
            try:
                body = raw.decode(charset, errors="replace")
            except LookupError:
                body = raw.decode("utf-8", errors="replace")

            return FetchResult(
                path=path,
                url=url,
                status=resp.status,
                final_url=resp.geturl(),
                content_type=resp.headers.get("Content-Type", ""),
                body=body,
                error=None,
                elapsed_ms=elapsed_ms,
            )

    except HTTPError as exc:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        try:
            body = exc.read().decode("utf-8", errors="replace")
        except Exception:
            body = ""
        return FetchResult(path, url, exc.code, exc.geturl(), exc.headers.get("Content-Type", ""), body, str(exc), elapsed_ms)

    except URLError as exc:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return FetchResult(path, url, None, None, "", str(exc.reason), elapsed_ms)

    except Exception as exc:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return FetchResult(path, url, None, None, "", repr(exc), elapsed_ms)


def status_icon(ok: bool) -> str:
    return "OK " if ok else "ERR"


def is_noindex(html: str) -> bool:
    parser = HeadParser()
    try:
        parser.feed(html[:100000])
    except Exception:
        return False
    return any("noindex" in content.lower() for content in parser.meta_robots)


def page_head_info(html: str) -> tuple[str, str, str]:
    parser = HeadParser()
    try:
        parser.feed(html[:150000])
    except Exception:
        return "", "", ""

    title = " ".join(parser.title.split())
    description = " ".join((parser.meta_descriptions[0] if parser.meta_descriptions else "").split())
    canonical = parser.canonicals[0] if parser.canonicals else ""
    return title, description, canonical


def check_robots(base_url: str, result: FetchResult) -> list[str]:
    problems = []
    body = result.body or ""

    if result.status != 200:
        problems.append(f"robots.txt status is {result.status}, expected 200.")
        return problems

    if "Sitemap:" not in body:
        problems.append("robots.txt does not contain a Sitemap: line.")

    bad_disallow = []
    for line in body.splitlines():
        compact = line.strip().replace(" ", "")
        if compact.lower() == "disallow:/":
            bad_disallow.append(line.strip())

    if bad_disallow:
        problems.append("robots.txt contains full Disallow: / rule.")

    expected_sitemap = urljoin(base_url, "sitemap.xml")
    if "Sitemap:" in body and expected_sitemap not in body:
        problems.append(f"robots.txt has Sitemap line, but not expected URL: {expected_sitemap}")

    return problems


def check_sitemap(base_url: str, result: FetchResult, expected_paths: list[str]) -> list[str]:
    problems = []
    body = result.body or ""

    if result.status != 200:
        problems.append(f"sitemap.xml status is {result.status}, expected 200.")
        return problems

    if "<urlset" not in body:
        problems.append("sitemap.xml does not look like a standard XML urlset.")

    missing = []
    for path in expected_paths:
        expected_url = urljoin(base_url, path.lstrip("/"))
        # Accept trailing slash variation for homepage.
        if expected_url not in body:
            missing.append(path)

    if missing:
        problems.append("Missing URLs in sitemap.xml: " + ", ".join(missing))

    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description="Check Austria Express SEO basics: 200 status, robots.txt and sitemap.xml.")
    parser.add_argument(
        "base_url",
        nargs="?",
        default="https://website-mq6h.onrender.com",
        help="Base URL, e.g. https://website-mq6h.onrender.com or http://127.0.0.1:5000",
    )
    parser.add_argument(
        "--path",
        action="append",
        default=[],
        help="Additional path to check. Can be used multiple times.",
    )
    parser.add_argument("--timeout", type=int, default=25)
    args = parser.parse_args()

    base_url = normalize_base_url(args.base_url)
    paths = list(dict.fromkeys(DEFAULT_PATHS + args.path))

    print("=" * 72)
    print("Austria Express SEO status check")
    print("Base URL:", base_url.rstrip("/"))
    print("=" * 72)

    results: dict[str, FetchResult] = {}
    has_error = False

    print("\nHTTP status")
    print("-" * 72)

    for path in paths:
        result = fetch(base_url, path, timeout=args.timeout)
        results[path] = result

        ok = result.status == 200
        if not ok:
            has_error = True

        redirect_note = ""
        if result.final_url and result.final_url.rstrip("/") != result.url.rstrip("/"):
            redirect_note = f" -> {result.final_url}"

        print(f"{status_icon(ok)} {path:<35} {str(result.status or 'NO RESPONSE'):<12} {result.elapsed_ms:>5} ms{redirect_note}")

        if result.error and not ok:
            print(f"    Error: {result.error}")

    print("\nPage head checks")
    print("-" * 72)

    for path, result in results.items():
        if not (result.status == 200 and "text/html" in result.content_type.lower()):
            continue

        title, description, canonical = page_head_info(result.body)
        noindex = is_noindex(result.body)

        title_ok = 10 <= len(title) <= 75
        desc_ok = 50 <= len(description) <= 180
        noindex_ok = not noindex

        if not title_ok or not desc_ok or not noindex_ok:
            has_error = True

        print(f"{status_icon(title_ok and desc_ok and noindex_ok)} {path}")
        print(f"    title: {title or '-'}")
        print(f"    description: {description or '-'}")
        print(f"    canonical: {canonical or '-'}")
        if noindex:
            print("    ERROR: page contains noindex")

    print("\nrobots.txt")
    print("-" * 72)
    robots_problems = check_robots(base_url, results.get("/robots.txt"))
    if robots_problems:
        has_error = True
        for problem in robots_problems:
            print("ERR", problem)
    else:
        print("OK robots.txt looks fine")

    print("\nsitemap.xml")
    print("-" * 72)
    sitemap_problems = check_sitemap(base_url, results.get("/sitemap.xml"), EXPECTED_SITEMAP_PATHS)
    if sitemap_problems:
        has_error = True
        for problem in sitemap_problems:
            print("ERR", problem)
    else:
        print("OK sitemap.xml contains expected URLs")

    print("\nSummary")
    print("-" * 72)
    if has_error:
        print("Result: ERR - please fix the reported items.")
        return 1

    print("Result: OK - basic SEO status checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
