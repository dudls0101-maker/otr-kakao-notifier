"""OTR 오디션 목록 크롤링 라이브러리.

Cloudflare Worker(otr-proxy)를 거쳐 OTR 게시판을 호출한다.
cupid.js 봇 챌린지는 Worker 측에서 같은 colo 안에서 1차+2차 fetch 로 자동 해결한다.
파이썬은 단순히 Worker URL 을 한 번 호출하면 정상 HTML 을 받는다.

환경변수:
- PROXY_URL: Cloudflare Worker URL (기본값: hard-coded fallback)
"""

import os
import re
from dataclasses import dataclass
from typing import List

import requests
from bs4 import BeautifulSoup


# Cloudflare Worker 기본 URL. GitHub Secrets 의 PROXY_URL 로 override 가능.
DEFAULT_PROXY_URL = "https://otr-proxy.dudls010.workers.dev"

# auditions.json 의 source 필드 등에 표시할 원본 URL (참조용)
AUDITION_URL = "https://otr.co.kr/audition/?mode=list"

VID_RE = re.compile(r"(?:[?&]|&amp;)vid=(\d+)")


@dataclass(frozen=True)
class Post:
    vid: int
    title: str
    url: str


def _proxy_url() -> str:
    return os.environ.get("PROXY_URL", DEFAULT_PROXY_URL).rstrip("/")


def _default_headers() -> dict:
    return {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) "
            "Version/17.4 Safari/605.1.15"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.7,en;q=0.6",
    }


def _is_cupid_challenge(html: str) -> bool:
    lowered = html.lower()
    return "cupid.js" in lowered and "tonumbers" in lowered


def _parse_posts_from_html(html: str) -> List[Post]:
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
        print(f"No posts parsed. snippet={snippet}")

    # dedupe by (vid, title)
    unique = {(p.vid, p.title): p for p in posts}
    posts = list(unique.values())
    posts.sort(key=lambda p: p.vid, reverse=True)
    return posts


def fetch_posts(timeout_seconds: int = 30) -> List[Post]:
    """OTR 오디션 목록을 Cloudflare Worker 프록시 경유로 가져온다.

    Worker 가 cupid 챌린지를 직접 해결하므로 파이썬은 한 번만 호출.
    """
    base = _proxy_url()
    print(f"Fetching via Cloudflare Worker: {base}")

    r = requests.get(
        f"{base}/?mode=list",
        headers=_default_headers(),
        timeout=timeout_seconds,
    )
    html = r.text

    if _is_cupid_challenge(html):
        print("Worker returned cupid challenge — Worker failed to handle it")
        snippet = html[:300].replace("\n", " ")
        print(f"snippet={snippet}")
        return []

    if "403 forbidden" in html.lower():
        snippet = html[:200].replace("\n", " ")
        print(f"403 Forbidden. snippet={snippet}")
        return []

    return _parse_posts_from_html(html)
