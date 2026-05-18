"""OTR 오디션 목록 크롤링 라이브러리.

Cloudflare Worker(otr-proxy)를 거쳐 OTR 게시판을 호출한다.
OTR 이 cupid.js JavaScript 챌린지(AES-CBC 한 블록 암호화 토큰)를 응답하면
파이썬에서 직접 복호화해 CUPID 쿠키를 만들고 ckattempt=1 으로 재요청한다.

환경변수:
- PROXY_URL: Cloudflare Worker URL (기본값: hard-coded fallback)
"""

import os
import re
from binascii import hexlify, unhexlify
from dataclasses import dataclass
from typing import List, Optional

import requests
from bs4 import BeautifulSoup
from Crypto.Cipher import AES


# Cloudflare Worker 기본 URL. GitHub Secrets 의 PROXY_URL 로 override 가능.
DEFAULT_PROXY_URL = "https://otr-proxy.dudls010.workers.dev"

# auditions.json 의 source 필드 등에 표시할 원본 URL (참조용)
AUDITION_URL = "https://otr.co.kr/audition/?mode=list"

VID_RE = re.compile(r"(?:[?&]|&amp;)vid=(\d+)")
CUPID_A_RE = re.compile(r'a\s*=\s*toNumbers\("([0-9a-f]+)"\)')
CUPID_B_RE = re.compile(r'b\s*=\s*toNumbers\("([0-9a-f]+)"\)')
CUPID_C_RE = re.compile(r'c\s*=\s*toNumbers\("([0-9a-f]+)"\)')


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


def _solve_cupid_challenge(html: str) -> Optional[str]:
    """cupid.js 챌린지 페이지에서 a, b, c hex 값 파싱 후 AES-CBC 복호화 → CUPID 토큰(hex)."""
    m_a = CUPID_A_RE.search(html)
    m_b = CUPID_B_RE.search(html)
    m_c = CUPID_C_RE.search(html)
    if not (m_a and m_b and m_c):
        return None

    key = unhexlify(m_a.group(1))       # AES key (16 bytes)
    iv = unhexlify(m_b.group(1))         # IV (16 bytes)
    cipher = unhexlify(m_c.group(1))     # ciphertext (정확히 1 블록 = 16 bytes)

    # slowAES 의 decrypt 는 padding 없는 raw 블록 복호화이므로
    # pycryptodome AES.MODE_CBC.decrypt 를 그대로 쓰면 동일한 결과가 나온다.
    aes = AES.new(key, AES.MODE_CBC, iv)
    plaintext = aes.decrypt(cipher)
    return hexlify(plaintext).decode("ascii")


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

    1) Worker URL 호출 → cupid 챌린지면 AES 복호화 → CUPID 토큰
    2) CUPID 쿠키 + ckattempt=1 로 재요청 → 정상 HTML
    3) HTML 파싱
    """
    base = _proxy_url()
    session = requests.Session()
    session.headers.update(_default_headers())

    print(f"Fetching via Cloudflare Worker: {base}")
    r1 = session.get(f"{base}/?mode=list", timeout=timeout_seconds)
    html = r1.text

    if _is_cupid_challenge(html):
        token = _solve_cupid_challenge(html)
        if not token:
            print("cupid challenge detected but could not parse a/b/c")
            return []
        print(f"cupid challenge solved, CUPID={token[:16]}...")

        # 2차 호출: 쿠키 + ckattempt=1
        r2 = session.get(
            f"{base}/?mode=list&ckattempt=1",
            headers={"Cookie": f"CUPID={token}"},
            timeout=timeout_seconds,
        )
        html = r2.text

        if _is_cupid_challenge(html):
            print("still got cupid challenge after solving. abort.")
            return []

    if "403 forbidden" in html.lower():
        snippet = html[:200].replace("\n", " ")
        print(f"403 Forbidden. snippet={snippet}")
        return []

    return _parse_posts_from_html(html)
