"""OTR 오디션 목록 크롤링 라이브러리.

`fetch_posts()` 를 호출하면 OTR 오디션 게시판의 글 목록을 가져온다.

OTR 은 GitHub Actions 데이터센터 IP 를 봇으로 차단(cupid.js → 403)하므로,
환경변수 `ZENROWS_API_KEY` 가 있으면 ZenRows 프록시(한국 IP + JS 렌더링)로
우회한다. 키가 없으면 기존 requests / Playwright 경로로 시도(로컬 개발용).
"""

import os
import re
from dataclasses import dataclass
from typing import List
from urllib.parse import urlencode

import requests
from bs4 import BeautifulSoup


AUDITION_URL = "https://otr.co.kr/audition/?mode=list"
VID_RE = re.compile(r"(?:[?&]|&amp;)vid=(\d+)")

ZENROWS_ENDPOINT = "https://api.zenrows.com/v1/"


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


def _looks_forbidden(html: str) -> bool:
    lowered = html.lower()
    return "403 forbidden" in lowered or "you don't have permission" in lowered


def _fetch_html_zenrows(api_key: str, timeout_seconds: int = 60) -> tuple[str, int, str]:
    """ZenRows API 로 한국 IP + JS 렌더링 우회."""
    params = {
        "apikey": api_key,
        "url": AUDITION_URL,
        "js_render": "true",
        "premium_proxy": "true",
        "proxy_country": "kr",
    }
    api_url = ZENROWS_ENDPOINT + "?" + urlencode(params)
    resp = requests.get(api_url, timeout=timeout_seconds)
    resp.raise_for_status()
    return resp.text, resp.status_code, AUDITION_URL


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
    """OTR 오디션 목록 글들을 가져온다.

    우선순위:
    1. ZENROWS_API_KEY 가 있으면 ZenRows 로 한국 IP + JS 렌더링 (운영용)
    2. 없으면 requests 직접 호출 (로컬에서 한국 IP 일 때만 작동)
    3. requests 가 봇 차단 페이지를 받으면 Playwright 폴백 (로컬 디버깅용)
    """
    api_key = os.environ.get("ZENROWS_API_KEY", "").strip()

    if api_key:
        print("Fetching via ZenRows (proxy_country=kr, js_render=true)...")
        html, status, source_url = _fetch_html_zenrows(api_key, timeout_seconds=60)
        if _looks_forbidden(html) or _looks_like_bot_challenge(html):
            print("ZenRows response still looks blocked. Will not retry locally on Actions.")
        return _parse_posts_from_html(html, status=status, source_url=source_url)

    # --- 로컬 개발 경로 ---
    print("ZENROWS_API_KEY not set. Falling back to direct requests (local dev mode).")
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
