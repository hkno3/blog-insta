"""
URL에 접속해서 제목, 본문, 대표 이미지(og:image)를 추출합니다.
"""
import io
import logging
import requests
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


def _upload_jpeg(buf: io.BytesIO) -> str | None:
    """변환된 JPEG를 여러 무료 호스트에 순차 업로드, 성공한 URL 반환."""

    # 1) catbox.moe
    buf.seek(0)
    try:
        r = requests.post(
            "https://catbox.moe/user/api.php",
            data={"reqtype": "fileupload"},
            files={"fileToUpload": ("image.jpg", buf, "image/jpeg")},
            timeout=20,
        )
        url = r.text.strip()
        if r.status_code == 200 and url.startswith("https://"):
            log.debug("catbox.moe 업로드 성공: %s", url)
            return url
    except Exception as e:
        log.debug("catbox.moe 실패: %s", e)

    # 2) 0x0.st
    buf.seek(0)
    try:
        r = requests.post(
            "https://0x0.st",
            files={"file": ("image.jpg", buf, "image/jpeg")},
            timeout=20,
        )
        url = r.text.strip()
        if r.status_code == 200 and url.startswith("https://"):
            log.debug("0x0.st 업로드 성공: %s", url)
            return url
    except Exception as e:
        log.debug("0x0.st 실패: %s", e)

    # 3) litterbox.catbox.moe (72시간 임시)
    buf.seek(0)
    try:
        r = requests.post(
            "https://litterbox.catbox.moe/resources/internals/api.php",
            data={"reqtype": "fileupload", "time": "72h"},
            files={"fileToUpload": ("image.jpg", buf, "image/jpeg")},
            timeout=20,
        )
        url = r.text.strip()
        if r.status_code == 200 and url.startswith("https://"):
            log.debug("litterbox 업로드 성공: %s", url)
            return url
    except Exception as e:
        log.debug("litterbox 실패: %s", e)

    return None


def _to_jpeg_url(image_url: str) -> str | None:
    """
    WebP 이미지를 Instagram이 지원하는 JPEG URL로 변환합니다.
    1. 쿼리 파라미터 제거 후 .webp 여부 확인
    2. .jpg / .jpeg 버전 URL 시도
    3. WebP 다운로드 → JPEG 변환 → 외부 호스팅 업로드 (3개 서비스 순차 시도)
    변환 불가 시 None 반환
    """
    base = image_url.split("?")[0]  # 쿼리 파라미터 제거해서 확장자 확인
    if not base.lower().endswith(".webp"):
        return image_url  # WebP 아니면 그대로 반환

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

    # 2단계: WebP 다운로드 → JPEG 변환 → 외부 호스트 업로드
    try:
        r = requests.get(image_url, headers=_HEADERS, timeout=20)
        r.raise_for_status()
        img = Image.open(io.BytesIO(r.content)).convert("RGB")
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=90)
        result = _upload_jpeg(buf)
        if result:
            return result
        log.warning("모든 이미지 호스팅 서비스 업로드 실패: %s", image_url)
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

    # 대표 이미지: og:image → twitter:image 순으로 탐색 후 WebP면 JPEG로 변환
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
        image_url = _to_jpeg_url(image_url)
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
