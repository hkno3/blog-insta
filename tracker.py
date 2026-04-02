"""
이미 인스타그램에 올린 글을 추적합니다.
중복 게시를 방지하기 위해 로컬 JSON 파일에 저장합니다.
"""
import json
import os
from datetime import datetime

_DATA_DIR = os.getenv("DATA_DIR", os.path.dirname(__file__))
TRACKER_FILE = os.path.join(_DATA_DIR, "published_posts.json")
FAILED_FILE = os.path.join(_DATA_DIR, "failed_posts.json")


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


def delete_published(wp_post_id: int) -> bool:
    """게시 이력에서 특정 글을 삭제합니다. 삭제 성공 시 True 반환."""
    data = _load()
    if str(wp_post_id) not in data:
        return False
    del data[str(wp_post_id)]
    _save(data)
    return True


def _load_failed() -> dict:
    if not os.path.exists(FAILED_FILE):
        return {}
    with open(FAILED_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_failed(data: dict) -> None:
    with open(FAILED_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def is_failed(wp_post_id: int) -> bool:
    """해당 글이 실패로 기록됐는지 확인합니다.
    429(할당량 초과) 실패는 오늘 실패한 경우만 스킵하고, 이전 날 실패면 재시도 허용합니다."""
    data = _load_failed()
    entry = data.get(str(wp_post_id))
    if entry is None:
        return False
    reason = entry.get("reason", "")
    if "429" in reason or "RESOURCE_EXHAUSTED" in reason:
        failed_date = entry.get("failed_at", "")[:10]  # YYYY-MM-DD
        today = datetime.now().strftime("%Y-%m-%d")
        return failed_date == today  # 오늘 실패 → 스킵, 이전 날 실패 → 재시도
    return True


def mark_failed(wp_post_id: int, post_title: str, reason: str) -> None:
    """게시 실패한 글을 기록합니다."""
    data = _load_failed()
    data[str(wp_post_id)] = {
        "title": post_title,
        "failed_at": datetime.now().isoformat(),
        "reason": reason,
    }
    _save_failed(data)


# ── URL 기반 추적 (Google Sheets 방식) ──────────────────────────────────────

def is_published_url(url: str) -> bool:
    """해당 URL이 이미 게시됐는지 확인합니다."""
    return url in _load()


def mark_published_url(url: str, instagram_media_id: str, post_title: str) -> None:
    """게시 완료된 URL을 기록합니다."""
    data = _load()
    data[url] = {
        "instagram_media_id": instagram_media_id,
        "title": post_title,
        "published_at": datetime.now().isoformat(),
    }
    _save(data)


def is_failed_url(url: str) -> bool:
    """해당 URL이 실패로 기록됐는지 확인합니다.
    429 실패는 오늘만 스킵하고 다음 날 재시도합니다."""
    entry = _load_failed().get(url)
    if entry is None:
        return False
    reason = entry.get("reason", "")
    if "429" in reason or "RESOURCE_EXHAUSTED" in reason:
        failed_date = entry.get("failed_at", "")[:10]
        today = datetime.now().strftime("%Y-%m-%d")
        return failed_date == today
    return True


def mark_failed_url(url: str, post_title: str, reason: str) -> None:
    """게시 실패한 URL을 기록합니다."""
    data = _load_failed()
    data[url] = {
        "title": post_title,
        "failed_at": datetime.now().isoformat(),
        "reason": reason,
    }
    _save_failed(data)
