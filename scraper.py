"""
URL에 접속해서 제목, 본문, 대표 이미지(og:image)를 추출합니다.
"""
import base64
import io
import logging
import os
import requests
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from PIL import Image

log = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


def _get_wp_jpeg_url(page_url: str) -> str | None:
    """
    WordPress REST API로 포스트의 원본 JPEG 이미지 URL을 가져옵니다.
    og:image가 WebP여도 업로드 원본이 JPEG인 경우 JPEG URL을 반환합니다.
    """
    parsed = urlparse(page_url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    slug = parsed.path.strip("/").split("/")[-1]
    if not slug:
        return None

    try:
        r = requests.get(
            f"{base}/wp-json/wp/v2/posts",
            params={"slug": slug, "_fields": "featured_media"},
            headers=_HEADERS,
            timeout=15,
        )
        if r.status_code != 200:
            return None
        posts = r.json()
        if not posts or not isinstance(posts, list):
            return None
        media_id = posts[0].get("featured_media")
        if not media_id:
            return None
    except Exception as e:
        log.debug("WP REST posts 조회 실패: %s", e)
        return None

    try:
        r = requests.get(
            f"{base}/wp-json/wp/v2/media/{media_id}",
            params={"_fields": "source_url,media_details"},
            headers=_HEADERS,
            timeout=15,
        )
        if r.status_code != 200:
            return None
        data = r.json()
    except Exception as e:
        log.debug("WP REST media 조회 실패: %s", e)
        return None

    sizes = data.get("media_details", {}).get("sizes", {})
    for size in ("large", "medium_large", "full"):
        url = sizes.get(size, {}).get("source_url", "")
        if url and not url.lower().split("?")[0].endswith(".webp"):
            log.debug("WP REST JPEG URL 발견 (%s): %s", size, url)
            return url

    source = data.get("source_url", "")
    if source and not source.lower().split("?")[0].endswith(".webp"):
        return source

    return None


def _upload_jpeg(buf: io.BytesIO) -> str | None:
    """변환된 JPEG를 imgbb에 업로드, 성공한 URL 반환."""
    api_key = os.getenv("IMGBB_API_KEY", "").strip()
    if not api_key:
        log.warning("IMGBB_API_KEY 없음")
        return None

    buf.seek(0)
    try:
        encoded = base64.b64encode(buf.read()).decode("utf-8")
        r = requests.post(
            "https://api.imgbb.com/1/upload",
            data={"key": api_key, "image": encoded},
            timeout=30,
        )
        data = r.json()
        if r.status_code == 200 and data.get("success"):
            return data["data"]["url"]
        log.warning("imgbb 업로드 실패: %s", data.get("error", {}).get("message", ""))
    except Exception as e:
        log.warning("imgbb 업로드 실패: %s", e)

    return None


def _to_jpeg_url(image_url: str, page_url: str | None = None) -> str | None:
    """
    WebP 이미지를 Instagram이 지원하는 JPEG URL로 변환합니다.
    1. .jpg / .jpeg 버전 URL 직접 시도
    2. WordPress REST API로 원본 JPEG URL 조회
    3. WebP 다운로드 → JPEG 변환 → imgbb 업로드
    변환 불가 시 None 반환
    """
    base = image_url.split("?")[0]
    if not base.lower().endswith(".webp"):
        return image_url

    # 1단계: .jpg / .jpeg 버전 URL 시도
    for ext in (".jpg", ".jpeg"):
        alt_url = base[:-5] + ext
        try:
            r = requests.head(alt_url, headers=_HEADERS, timeout=10)
            if r.status_code == 200:
                log.debug("JPEG 버전 URL 발견: %s", alt_url)
                return alt_url
        except Exception:
            pass

    # 2단계: WordPress REST API로 원본 JPEG 조회
    if page_url:
        jpeg_url = _get_wp_jpeg_url(page_url)
        if jpeg_url:
            return jpeg_url

    # 3단계: WebP 다운로드 → JPEG 변환 → imgbb 업로드
    try:
        r = requests.get(image_url, headers=_HEADERS, timeout=20)
        r.raise_for_status()
        img = Image.open(io.BytesIO(r.content)).convert("RGB")
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=90)
        result = _upload_jpeg(buf)
        if result:
            return result
        log.warning("imgbb 업로드 실패: %s", image_url)
    except Exception as e:
        log.warning("WebP 변환 실패: %s", e)

    return None


def scrape_post(url: str) -> dict | None:
    """
    URL을 스크래핑해서 포스트 정보를 반환합니다.

    Returns:
        {"url", "title", "plain_text", "image_url"} 또는 None (실패 시)
    """
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=20)
        resp.raise_for_status()
    except Exception as e:
        raise RuntimeError(f"페이지 접속 실패: {e}")

    soup = BeautifulSoup(resp.text, "lxml")

    # 제목: og:title → <title> 순으로 시도
    og_title = soup.find("meta", property="og:title")
    if og_title and og_title.get("content"):
        title = og_title["content"].strip()
    elif soup.title:
        title = soup.title.string.strip() if soup.title.string else ""
    else:
        title = ""

    # 대표 이미지: og:image → og:image:secure_url → twitter:image 순으로 탐색
    image_url = None
    for selector in [
        {"property": "og:image"},
        {"property": "og:image:secure_url"},
        {"name": "twitter:image"},
    ]:
        tag = soup.find("meta", selector)
        if tag and tag.get("content", "").strip():
            image_url = tag["content"].strip()
            break

    if image_url:
        image_url = _to_jpeg_url(image_url, page_url=url)
        if image_url:
            log.debug("최종 이미지 URL: %s", image_url)

    # 본문: WordPress 일반적인 클래스명 순으로 탐색
    content_div = (
        soup.find(class_="entry-content")
        or soup.find(class_="post-content")
        or soup.find(class_="article-content")
        or soup.find("article")
    )
    if content_div:
        for tag in content_div(["script", "style", "figure", "iframe", "nav"]):
            tag.decompose()
        lines = [
            line.strip()
            for line in content_div.get_text(separator="\n").splitlines()
            if line.strip()
        ]
        plain_text = "\n".join(lines)
    else:
        plain_text = ""

    return {
        "url": url,
        "title": title,
        "plain_text": plain_text,
        "image_url": image_url,
    }
