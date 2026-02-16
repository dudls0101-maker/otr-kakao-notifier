# OTR 뮤지컬 오디션 카카오 알림

`https://otr.co.kr/audition/`에 새 글이 올라왔을 때 **제목에 `뮤지컬`이 포함**되면 카카오톡 **나에게 보내기**로 알림을 보냅니다.

## 동작 방식
- 1시간마다 실행 (GitHub Actions `cron`)
- 글 목록에서 `vid`를 파싱
- `state.json`의 `last_vid` 보다 큰 글만 신규로 간주
- 신규 글 중 제목에 `뮤지컬` 포함 시 카카오톡 알림 전송
- 실행 후 `state.json` 갱신 및 커밋

## 준비물
- GitHub 계정
- Kakao Developers 앱 (REST API 키 필요)

## 1) Kakao Developers 설정
1. https://developers.kakao.com/ 접속
2. 내 애플리케이션 생성
3. **앱 키**에서 `REST API 키` 확인
4. **카카오 로그인 > 동의항목**에서
   - `카카오톡 메시지 전송`(talk_message) 사용 동의가 필요합니다.

## 2) Refresh Token 발급 (로컬 1회)
로컬 PC에서 한 번만 `refresh_token`을 발급받아 GitHub Secrets에 넣습니다.

### (1) Redirect URI 준비
Kakao OAuth는 redirect URI가 필요합니다.
가장 쉬운 방법은 임시로 아래를 쓰는 겁니다.
- `https://example.com/oauth`

그리고 Kakao Developers 콘솔에서
- **카카오 로그인 > Redirect URI**에 위 값을 추가하세요.

### (2) 토큰 발급 스크립트 실행
PowerShell 예시:
```powershell
$env:KAKAO_REST_API_KEY="여기에_REST_API_KEY"
$env:KAKAO_REDIRECT_URI="https://example.com/oauth"
python -m pip install -r requirements.txt
python tools/get_kakao_refresh_token.py
```

출력되는 로그인 URL을 브라우저로 열고 동의 후, redirect된 URL의 `code` 값을 복사해 입력하면 `refresh_token`이 출력됩니다.

## 3) GitHub Repo 생성 및 Secrets 등록
1. 이 폴더를 GitHub 새 리포로 푸시
2. GitHub Repo > Settings > Secrets and variables > Actions > New repository secret
3. 아래 2개를 등록
- `KAKAO_REST_API_KEY`
- `KAKAO_REFRESH_TOKEN`

## 4) GitHub Actions 실행 확인
- Actions 탭에서 워크플로가 매시간 실행됩니다.
- 처음 실행 시에는 `state.json`만 갱신되고(또는 신규 글이 있으면 알림) 이후부터는 새 글만 감지합니다.
- Actions 실행 목록에서 이벤트 필터가 `event:workflow_dispatch`로 걸려 있으면 스케줄 실행(`event:schedule`)이 보이지 않습니다. 필터를 지우고 확인하세요.
- Event 드롭다운에서 `workflow_dispatch`가 선택된 상태여도 수동 실행만 보입니다. 드롭다운 우측 `X`로 필터를 해제하세요.

## 주의
- Kakao 토큰/키는 **절대 커밋하지 말고** GitHub Secrets로만 관리하세요.
- GitHub Actions는 크론이 정확히 정시 실행이 아니라 약간 지연될 수 있습니다.
