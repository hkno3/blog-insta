"""
WordPress REST API 클라이언트
공개된 글을 가져와서 내용을 파싱합니다.
"""
import os
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

WP_SITE_URL = os.getenv("WP_SITE_URL", "").rstrip("/")
WP_USERNAME = os.getenv("WP_USERNAME", "")
WP_APP_PASSWORD = os.getenv("WP_APP_PASSWORD", "")


def _get_auth():
    if WP_USERNAME and WP_APP_PASSWORD:
        return (WP_USERNAME, WP_APP_PASSWORD)
    return None


_HEADERS = {"Accept": "application/json", "Content-Type": "application/json"}


def get_recent_posts(count: int = 10) -> list[dict]:
    """최근 워드프레스 글 목록을 가져옵니다."""
    url = f"{WP_SITE_URL}/wp-json/wp/v2/posts"
    params = {
        "per_page": count,
        "orderby": "date",
        "order": "desc",
        "status": "publish",
        "_fields": "id,date,title,link,content,excerpt,featured_media,categories",
    }
    resp = requests.get(url, params=params, auth=_get_auth(), headers=_HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.json()


def get_featured_image_url(post: dict) -> str | None:
    """글의 대표 이미지 URL을 가져옵니다."""
    media_id = post.get("featured_media")
    if not media_id:
        return None
    url = f"{WP_SITE_URL}/wp-json/wp/v2/media/{media_id}"
    try:
        resp = requests.get(url, auth=_get_auth(), headers=_HEADERS, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        # 적절한 크기 선택 (large > medium_large > full)
        sizes = data.get("media_details", {}).get("sizes", {})
        for size in ("large", "medium_large", "full"):
            if size in sizes:
                return sizes[size]["source_url"]
        return data.get("source_url")
    except Exception:
        return None


def extract_plain_text(html_content: str) -> str:
    """HTML 본문에서 순수 텍스트를 추출합니다."""
    soup = BeautifulSoup(html_content, "lxml")
    # 불필요한 태그 제거
    for tag in soup(["script", "style", "figure", "iframe"]):
        tag.decompose()
    text = soup.get_text(separator="\n")
    # 빈 줄 정리
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return "\n".join(lines)


def parse_post(raw: dict) -> dict:
    """API 응답을 정리된 딕셔너리로 변환합니다."""
    return {
        "id": raw["id"],
        "date": raw["date"],
        "title": raw["title"]["rendered"],
        "url": raw["link"],
        "plain_text": extract_plain_text(raw["content"]["rendered"]),
        "excerpt": BeautifulSoup(
            raw["excerpt"]["rendered"], "lxml"
        ).get_text().strip(),
        "featured_media_id": raw.get("featured_media"),
    }
