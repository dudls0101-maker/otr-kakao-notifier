# OTR 뮤지컬 오디션 JSON 빌더

[OTR 오디션 게시판](https://otr.co.kr/audition/?mode=list)에서 제목에 **"뮤지컬"**이 포함된 글을 자동으로 수집해 `auditions.json` 파일로 누적 저장한다. iOS(또는 다른) 앱이 이 JSON 한 파일만 fetch 하면 현재 등록된 뮤지컬 오디션 목록을 받아볼 수 있다.

## 동작 방식

- GitHub Actions(`build_auditions.yml`)가 30분마다 자동 실행
- 워크플로우가 `python -m src.build_auditions` 호출
  1. `src/check_otr_audition.py` 의 `fetch_posts()` 가 OTR 목록을 긁는다 (requests → 봇 차단 시 Playwright 폴백)
  2. 제목에 "뮤지컬"이 들어간 글만 필터링
  3. 기존 `auditions.json` 과 vid 기준으로 머지 (`first_seen_at` 보존, `last_seen_at` 갱신)
- 변경된 경우에만 `auditions.json` 을 자동 커밋

## `auditions.json` 스키마

```json
{
  "updated_at": "2026-05-17T12:00:00+00:00",
  "count": 12,
  "keyword": "뮤지컬",
  "source": "https://otr.co.kr/audition/?mode=list",
  "auditions": [
    {
      "vid": 20366,
      "title": "[뮤지컬 OOO] 앙상블 오디션",
      "url": "https://otr.co.kr/audition/?mode=view&vid=20366",
      "first_seen_at": "2026-05-17T12:00:00+00:00",
      "last_seen_at": "2026-05-17T15:00:00+00:00"
    }
  ]
}
```

`auditions` 배열은 `vid` 내림차순(최신 위) 정렬.

## 앱에서 fetch 하는 URL

두 가지 옵션 중 하나:

- **raw**: `https://raw.githubusercontent.com/dudls0101-maker/otr-kakao-notifier/main/auditions.json`
  - 즉시 사용 가능, 별도 설정 불필요
- **GitHub Pages (권장)**: `https://dudls0101-maker.github.io/otr-kakao-notifier/auditions.json`
  - Settings → Pages 에서 활성화 필요
  - CDN 캐싱이 붙어 트래픽에 더 강함

## 로컬 실행

```bash
pip install -r requirements.txt
python -m playwright install chromium
python -m src.build_auditions
```

실행 후 레포 루트에 `auditions.json` 이 생성/갱신된다.

## 알아둘 점

- GitHub Actions 의 `schedule` cron 은 정확한 정시 실행이 아니라 보통 5~15분 지연될 수 있다.
- OTR 사이트가 가끔 봇 차단(cupid.js)을 띄우면 Playwright 로 자동 폴백하므로 워크플로우 실행 시간이 늘어날 수 있다.
- 같은 vid 가 다시 떠도 `first_seen_at` 은 보존되므로 "처음 발견된 시점" 추적이 가능하다.
- OTR 목록에서 사라진 과거 글도 `auditions.json` 에서는 그대로 유지된다 (앱 쪽에서 마감일 기준 필터링하면 됨).
