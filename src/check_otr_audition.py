import json
import os
import re
from dataclasses import dataclass
from typing import Iterable, List, Tuple

import requests
from bs4 import BeautifulSoup

from .kakao_api import send_message_using_env


AUDITION_URL = "https://otr.co.kr/audition/"
VID_RE = re.compile(r"(?:[?&]|&amp;)vid=(\d+)")


@dataclass(frozen=True)
class Post:
    vid: int
    title: str
    url: str


def load_state(path: str) -> dict:
    if not os.path.exists(path):
        return {"last_vid": 0}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_state(path: str, state: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
        f.write("\n")


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
    return "cupid.js" in lowered or "toNumbers" in lowered


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
        url = page.url
        context.close()
        browser.close()
        return html, status, url


def _parse_posts_from_html(html: str, *, status: int, url: str) -> List[Post]:
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
        url = href
        if url.startswith("/"):
            url = "https://otr.co.kr" + url
        posts.append(Post(vid=vid, title=title, url=url))

    if not posts:
        snippet = html
        snippet = snippet.replace("\r", " ").replace("\n", " ")
        snippet = snippet[:400]
        print(f"No posts parsed. status={status} url={url} snippet={snippet}")

    unique = {(p.vid, p.title): p for p in posts}
    posts = list(unique.values())
    posts.sort(key=lambda p: p.vid, reverse=True)
    return posts


def fetch_posts(timeout_seconds: int = 20) -> List[Post]:
    html, status, url = _fetch_html_requests(timeout_seconds=timeout_seconds)

    if _looks_like_bot_challenge(html):
        print("Bot challenge detected (cupid.js). Falling back to Playwright...")
        html, status, url = _fetch_html_playwright(timeout_seconds=30)

    posts = _parse_posts_from_html(html, status=status, url=url)
    if not posts and not _looks_like_bot_challenge(html):
        print("No posts found via requests. Trying Playwright as a fallback...")
        html2, status2, url2 = _fetch_html_playwright(timeout_seconds=30)
        posts = _parse_posts_from_html(html2, status=status2, url=url2)

    return posts


def detect_new_posts(posts: Iterable[Post], last_vid: int) -> Tuple[List[Post], int]:
    max_vid = last_vid
    new_posts: List[Post] = []

    for p in posts:
        if p.vid > max_vid:
            max_vid = p.vid
        if p.vid > last_vid:
            new_posts.append(p)

    new_posts.sort(key=lambda p: p.vid)
    return new_posts, max_vid


def main() -> None:
    state_path = os.path.join(os.path.dirname(__file__), "..", "state.json")
    state_path = os.path.abspath(state_path)

    state = load_state(state_path)
    last_vid = int(state.get("last_vid", 0))

    posts = fetch_posts()
    new_posts, max_vid = detect_new_posts(posts, last_vid=last_vid)

    print(f"last_vid={last_vid} fetched={len(posts)} new_posts={len(new_posts)}")

    if os.environ.get("KAKAO_TEST_MESSAGE") == "1":
        send_message_using_env(text="[OTR 오디션] 테스트 메시지", url=AUDITION_URL)

    musical_posts = [p for p in new_posts if "뮤지컬" in p.title]
    print(f"musical_matches={len(musical_posts)}")

    if musical_posts:
        lines = [f"[OTR 오디션] 뮤지컬 신규 {len(musical_posts)}건"]
        for p in musical_posts:
            lines.append(f"- {p.title}")
            lines.append(p.url)
        text = "\n".join(lines)
        if len(text) > 900:
            text = text[:900] + "\n(이하 생략)"
        send_message_using_env(text=text, url=musical_posts[-1].url)

    if max_vid != last_vid:
        state["last_vid"] = max_vid
        save_state(state_path, state)


if __name__ == "__main__":
    main()
