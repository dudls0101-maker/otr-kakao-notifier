"""OTR 오디션 목록 크롤링 라이브러리.

`fetch_posts()` 를 호출하면 OTR 오디션 게시판의 글 목록을 가져온다.
사이트가 봇 차단(cupid.js)을 띄우는 경우 자동으로 Playwright(Chromium)로 폴백한다.
"""

import re
from dataclasses import dataclass
from typing import List

import requests
from bs4 import BeautifulSoup


AUDITION_URL = "https://otr.co.kr/audition/?mode=list"
VID_RE = re.compile(r"(?:[?&]|&amp;)vid=(\d+)")


@dataclass(frozen=True)
class Post:
    vid: int
    title: str
    url: str


def _default_headers() -> dict:
    return {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.7,en;q=0.6",
    }


def _looks_like_bot_challenge(html: str) -> bool:
    lowered = html.lower()
    return "cupid.js" in lowered or "tonumbers" in lowered


def _fetch_html_requests(timeout_seconds: int = 20) -> tuple[str, int, str]:
    resp = requests.get(AUDITION_URL, headers=_default_headers(), timeout=timeout_seconds)
    resp.raise_for_status()
    return resp.text, resp.status_code, resp.url


def _fetch_html_playwright(timeout_seconds: int = 30) -> tuple[str, int, str]:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=_default_headers()["User-Agent"],
            locale="ko-KR",
        )
        page = context.new_page()
        page.set_default_timeout(timeout_seconds * 1000)
        resp = page.goto(AUDITION_URL, wait_until="domcontentloaded")
        page.wait_for_timeout(3000)
        html = page.content()
        status = resp.status if resp else 0
        page_url = page.url
        context.close()
        browser.close()
        return html, status, page_url


def _parse_posts_from_html(html: str, *, status: int, source_url: str) -> List[Post]:
    soup = BeautifulSoup(html, "html.parser")

    posts: List[Post] = []
    for a in soup.find_all("a", href=True):
        href = a.get("href")
        if not href:
            continue
        m = VID_RE.search(href)
        if not m:
            continue

        title = a.get_text(strip=True)
        if not title:
            continue

        vid = int(m.group(1))
        link = href
        if link.startswith("/"):
            link = "https://otr.co.kr" + link
        posts.append(Post(vid=vid, title=title, url=link))

    if not posts:
        snippet = html.replace("\r", " ").replace("\n", " ")[:400]
        print(f"No posts parsed. status={status} url={source_url} snippet={snippet}")

    # dedupe by (vid, title)
    unique = {(p.vid, p.title): p for p in posts}
    posts = list(unique.values())
    posts.sort(key=lambda p: p.vid, reverse=True)
    return posts


def fetch_posts(timeout_seconds: int = 20) -> List[Post]:
    """OTR 오디션 목록 글들을 가져온다. requests 우선 시도, 봇 차단되면 Playwright 폴백."""
    html, status, source_url = _fetch_html_requests(timeout_seconds=timeout_seconds)

    if _looks_like_bot_challenge(html):
        print("Bot challenge detected (cupid.js). Falling back to Playwright...")
        html, status, source_url = _fetch_html_playwright(timeout_seconds=30)

    posts = _parse_posts_from_html(html, status=status, source_url=source_url)
    if not posts and not _looks_like_bot_challenge(html):
        print("No posts found via requests. Trying Playwright as a fallback...")
        html2, status2, url2 = _fetch_html_playwright(timeout_seconds=30)
        posts = _parse_posts_from_html(html2, status=status2, source_url=url2)

    return posts
