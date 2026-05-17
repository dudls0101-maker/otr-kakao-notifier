"""OTR 오디션 사이트에서 뮤지컬 공고를 긁어 auditions.json 으로 누적 저장.

iOS 앱이 fetch 할 수 있도록 레포 루트에 auditions.json 을 만들고 유지한다.
- 매 실행 시 OTR 목록을 새로 가져와 제목에 '뮤지컬'이 포함된 공고만 남김
- 기존 JSON 과 머지: 처음 본 공고는 추가, 이미 있는 공고는 title/url/last_seen_at 만 갱신
- 결과 JSON 은 GitHub Actions 가 자동 커밋 → GitHub Pages 또는 raw.githubusercontent.com 으로 노출
"""

import json
import os
from datetime import datetime, timezone
from typing import Dict, List

from .check_otr_audition import AUDITION_URL, Post, fetch_posts


# docs/ 안에 두면 GitHub Pages 가 같은 도메인에서 서빙해주므로
# PWA 가 동일 origin 으로 fetch 할 수 있다 (CORS 문제 없음).
AUDITIONS_JSON = "docs/auditions.json"
KEYWORD = "뮤지컬"


def _now_iso() -> str:
    # UTC ISO8601, e.g. "2026-05-17T12:34:56+00:00"
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_auditions(path: str) -> dict:
    if not os.path.exists(path):
        return {"updated_at": None, "count": 0, "auditions": []}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_auditions(path: str, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def merge(existing: List[dict], scraped: List[Post]) -> List[dict]:
    """vid 기준으로 머지.

    - 기존에 있던 공고: title/url/last_seen_at 만 갱신, first_seen_at 은 보존
    - 처음 보는 공고: 신규로 추가 (first_seen_at = last_seen_at = 지금)
    - 더 이상 OTR 목록에 안 보이는 과거 공고도 JSON 에는 그대로 남는다
      (앱에서 마감일 기준 필터링하면 되고, 사라진 글을 디스플레이해도 큰 문제 없음)
    """
    by_vid: Dict[int, dict] = {a["vid"]: a for a in existing}
    now = _now_iso()
    for p in scraped:
        if p.vid in by_vid:
            entry = by_vid[p.vid]
            entry["title"] = p.title
            entry["url"] = p.url
            entry["last_seen_at"] = now
        else:
            by_vid[p.vid] = {
                "vid": p.vid,
                "title": p.title,
                "url": p.url,
                "first_seen_at": now,
                "last_seen_at": now,
            }
    merged = list(by_vid.values())
    merged.sort(key=lambda a: a["vid"], reverse=True)  # 최신 vid 가 위
    return merged


def main() -> None:
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    path = os.path.join(root, AUDITIONS_JSON)

    existing_data = load_auditions(path)
    existing = existing_data.get("auditions", [])

    posts = fetch_posts()
    musical_posts = [p for p in posts if KEYWORD in p.title]
    print(f"fetched={len(posts)} musical={len(musical_posts)} existing={len(existing)}")

    merged = merge(existing, musical_posts)

    new_data = {
        "updated_at": _now_iso(),
        "count": len(merged),
        "keyword": KEYWORD,
        "source": AUDITION_URL,
        "auditions": merged,
    }
    save_auditions(path, new_data)
    print(f"saved {AUDITIONS_JSON}: {len(merged)} entries")


if __name__ == "__main__":
    main()
