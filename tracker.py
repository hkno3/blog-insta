"""
이미 인스타그램에 올린 글을 추적합니다.
중복 게시를 방지하기 위해 로컬 JSON 파일에 저장합니다.
"""
import json
import os
from datetime import datetime

TRACKER_FILE = os.path.join(os.path.dirname(__file__), "published_posts.json")


def _load() -> dict:
    if not os.path.exists(TRACKER_FILE):
        return {}
    with open(TRACKER_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save(data: dict) -> None:
    with open(TRACKER_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def is_published(wp_post_id: int) -> bool:
    """해당 워드프레스 글이 이미 게시됐는지 확인합니다."""
    data = _load()
    return str(wp_post_id) in data


def mark_published(wp_post_id: int, instagram_media_id: str, post_title: str) -> None:
    """게시 완료된 글을 기록합니다."""
    data = _load()
    data[str(wp_post_id)] = {
        "instagram_media_id": instagram_media_id,
        "title": post_title,
        "published_at": datetime.now().isoformat(),
    }
    _save(data)


def get_all_published() -> dict:
    """게시된 모든 글 목록을 반환합니다."""
    return _load()
