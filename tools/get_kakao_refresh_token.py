import os
import sys
from urllib.parse import quote

import requests


def main() -> None:
    rest_api_key = os.environ.get("KAKAO_REST_API_KEY")
    redirect_uri = os.environ.get("KAKAO_REDIRECT_URI")
    client_secret = os.environ.get("KAKAO_CLIENT_SECRET")

    if not rest_api_key:
        print("Missing env KAKAO_REST_API_KEY")
        sys.exit(1)
    if not redirect_uri:
        print("Missing env KAKAO_REDIRECT_URI")
        sys.exit(1)

    scope = "talk_message"
    auth_url = (
        "https://kauth.kakao.com/oauth/authorize"
        f"?client_id={quote(rest_api_key)}"
        f"&redirect_uri={quote(redirect_uri, safe='')}"
        "&response_type=code"
        f"&scope={quote(scope)}"
    )

    print("1) Open this URL in a browser and login to Kakao:")
    print(auth_url)
    print("\n2) After consent, you will be redirected to REDIRECT_URI with ?code=... in the URL.")
    code = input("\nPaste the code value here: ").strip()
    if not code:
        print("No code provided")
        sys.exit(1)

    resp = requests.post(
        "https://kauth.kakao.com/oauth/token",
        data={
            "grant_type": "authorization_code",
            "client_id": rest_api_key,
            **({"client_secret": client_secret} if client_secret else {}),
            "redirect_uri": redirect_uri,
            "code": code,
        },
        timeout=20,
    )
    if not resp.ok:
        print(f"HTTP {resp.status_code}: {resp.text}")
        resp.raise_for_status()
    data = resp.json()

    print("\nSave these to GitHub repo Secrets:")
    print(f"KAKAO_REST_API_KEY = {rest_api_key}")
    print(f"KAKAO_REFRESH_TOKEN = {data.get('refresh_token')}")


if __name__ == "__main__":
    main()
