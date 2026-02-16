import json
import os
import re
from dataclasses import dataclass
from typing import Iterable, List, Tuple

import requests
from bs4 import BeautifulSoup

from .kakao_api import send_message_using_env


AUDITION_URL = "https://otr.co.kr/audition/"
VID_RE = re.compile(r"[?&]vid=(\d+)")


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


def fetch_posts(timeout_seconds: int = 20) -> List[Post]:
    resp = requests.get(AUDITION_URL, timeout=timeout_seconds)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")

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

    unique = {(p.vid, p.title): p for p in posts}
    posts = list(unique.values())
    posts.sort(key=lambda p: p.vid, reverse=True)
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

    for p in new_posts:
        if "뮤지컬" in p.title:
            text = f"[OTR 오디션] {p.title}\n{p.url}"
            send_message_using_env(text=text, url=p.url)

    if max_vid != last_vid:
        state["last_vid"] = max_vid
        save_state(state_path, state)


if __name__ == "__main__":
    main()
