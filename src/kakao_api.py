import json
import os
from typing import Optional

import requests


def get_access_token(*, rest_api_key: str, refresh_token: str, timeout_seconds: int = 20) -> str:
    resp = requests.post(
        "https://kauth.kakao.com/oauth/token",
        data={
            "grant_type": "refresh_token",
            "client_id": rest_api_key,
            "refresh_token": refresh_token,
        },
        timeout=timeout_seconds,
    )
    resp.raise_for_status()
    data = resp.json()
    access_token = data.get("access_token")
    if not access_token:
        raise RuntimeError(f"No access_token in response: {data}")
    return access_token


def send_to_me(
    *,
    access_token: str,
    text: str,
    web_url: Optional[str] = None,
    mobile_web_url: Optional[str] = None,
    timeout_seconds: int = 20,
) -> None:
    link = {}
    if web_url:
        link["web_url"] = web_url
    if mobile_web_url:
        link["mobile_web_url"] = mobile_web_url

    template_object = {
        "object_type": "text",
        "text": text,
        "link": link or {"web_url": "https://otr.co.kr/audition/"},
        "button_title": "보기",
    }

    resp = requests.post(
        "https://kapi.kakao.com/v2/api/talk/memo/default/send",
        headers={"Authorization": f"Bearer {access_token}"},
        data={"template_object": json.dumps(template_object, ensure_ascii=False)},
        timeout=timeout_seconds,
    )
    resp.raise_for_status()


def send_message_using_env(*, text: str, url: Optional[str] = None) -> None:
    rest_api_key = os.environ.get("KAKAO_REST_API_KEY")
    refresh_token = os.environ.get("KAKAO_REFRESH_TOKEN")

    if not rest_api_key:
        raise RuntimeError("Missing env KAKAO_REST_API_KEY")
    if not refresh_token:
        raise RuntimeError("Missing env KAKAO_REFRESH_TOKEN")

    access_token = get_access_token(rest_api_key=rest_api_key, refresh_token=refresh_token)
    send_to_me(access_token=access_token, text=text, web_url=url, mobile_web_url=url)
