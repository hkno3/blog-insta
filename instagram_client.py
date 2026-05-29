"""
Instagram Graph API 클라이언트
Meta Business Suite의 Instagram Graph API를 사용합니다.

사전 준비:
1. Instagram 계정을 비즈니스/크리에이터 계정으로 전환
2. Facebook 페이지와 연결
3. Meta Developer App 생성 후 instagram_basic, instagram_content_publish 권한 요청
4. Long-lived Access Token 발급 (60일 유효, 갱신 가능)
"""
import os
import time
import requests
from dotenv import load_dotenv

load_dotenv()

GRAPH_API_BASE = "https://graph.instagram.com/v21.0"


def _api(method: str, endpoint: str, **kwargs) -> dict:
    access_token = os.getenv("INSTAGRAM_ACCESS_TOKEN", "").strip()
    url = f"{GRAPH_API_BASE}/{endpoint}"
    params = kwargs.pop("params", {})
    params["access_token"] = access_token
    resp = getattr(requests, method)(url, params=params, timeout=30, **kwargs)
    if not resp.ok:
        try:
            err_data = resp.json()
            if "error" in err_data:
                err = err_data["error"]
                code = err.get("code", "?")
                msg = err.get("message", "?")
                etype = err.get("type", "?")
                raise RuntimeError(f"Instagram API 오류 (HTTP {resp.status_code}, 코드 {code}, {etype}): {msg}")
        except (ValueError, KeyError):
            pass
        resp.raise_for_status()
    data = resp.json()
    if "error" in data:
        raise RuntimeError(f"Instagram API 오류: {data['error']['message']}")
    return data


def create_image_container(image_url: str, caption: str) -> str:
    """
    이미지 미디어 컨테이너를 생성합니다.
    이미지는 공개적으로 접근 가능한 URL이어야 합니다.

    Returns:
        creation_id (게시에 사용할 컨테이너 ID)
    """
    account_id = os.getenv("INSTAGRAM_BUSINESS_ACCOUNT_ID", "").strip()
    data = _api(
        "post",
        f"{account_id}/media",
        data={
            "image_url": image_url,
            "caption": caption,
        },
    )
    return data["id"]


def publish_container(creation_id: str) -> str:
    """
    생성된 컨테이너를 실제로 게시합니다.

    Returns:
        게시된 미디어 ID
    """
    account_id = os.getenv("INSTAGRAM_BUSINESS_ACCOUNT_ID", "").strip()
    data = _api(
        "post",
        f"{account_id}/media_publish",
        data={"creation_id": creation_id},
    )
    return data["id"]


def wait_for_container(creation_id: str, max_wait: int = 60) -> None:
    """컨테이너가 FINISHED 상태가 될 때까지 대기합니다."""
    for _ in range(max_wait // 5):
        data = _api("get", creation_id, params={"fields": "status_code,status"})
        status = data.get("status_code", "")
        if status == "FINISHED":
            return
        if status == "ERROR":
            raise RuntimeError(f"컨테이너 처리 오류: {data.get('status')}")
        time.sleep(5)
    raise RuntimeError("컨테이너 준비 시간 초과 (60초)")


def post_to_instagram(image_url: str, caption: str) -> str:
    """
    이미지와 캡션으로 인스타그램에 게시합니다.

    Args:
        image_url: 공개 접근 가능한 이미지 URL (워드프레스 미디어 URL)
        caption: 인스타그램 캡션 텍스트

    Returns:
        게시된 미디어 ID
    """
    creation_id = create_image_container(image_url, caption)
    wait_for_container(creation_id)
    media_id = publish_container(creation_id)
    return media_id


def get_account_info() -> dict:
    """계정 정보를 가져와 연결 상태를 확인합니다."""
    account_id = os.getenv("INSTAGRAM_BUSINESS_ACCOUNT_ID", "").strip()
    return _api("get", account_id, params={"fields": "id,username,name"})


def refresh_access_token() -> dict:
    """
    Long-lived token을 갱신합니다. (만료 30일 전부터 갱신 가능)
    갱신된 토큰 정보를 반환합니다.
    """
    data = _api(
        "get",
        "oauth/access_token",
        params={
            "grant_type": "fb_exchange_token",
            "client_id": os.getenv("META_APP_ID", ""),
            "client_secret": os.getenv("META_APP_SECRET", ""),
            "fb_exchange_token": os.getenv("INSTAGRAM_ACCESS_TOKEN", ""),
        },
    )
    return data
