"""
URL에 접속해서 제목, 본문, 대표 이미지(og:image)를 추출합니다.
"""
import io
import requests
from bs4 import BeautifulSoup
from PIL import Image


def _to_jpeg_url(page_url: str, image_url: str) -> str | None:
    """
    WebP 이미지를 Instagram이 지원하는 JPEG URL로 변환합니다.
    1. .jpg 버전 URL 시도
    2. WebP 다운로드 → JPEG 변환 → catbox.moe 임시 업로드
    변환 불가 시 None 반환
    """
    if not image_url.lower().endswith(".webp"):
        return image_url

    # 1단계: .jpg 버전 URL 시도
    jpg_url = image_url[:-5] + ".jpg"
    try:
        resp = requests.head(jpg_url, headers=_HEADERS, timeout=10)
        if resp.status_code == 200:
            return jpg_url
    except Exception:
        pass

    # 2단계: WebP 다운로드 → JPEG 변환 → catbox.moe 업로드
    try:
        resp = requests.get(image_url, headers=_HEADERS, timeout=20)
        resp.raise_for_status()

        img = Image.open(io.BytesIO(resp.content)).convert("RGB")
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=90)
        buf.seek(0)

        upload = requests.post(
            "https://catbox.moe/user/api.php",
            data={"reqtype": "fileupload"},
            files={"fileToUpload": ("image.jpg", buf, "image/jpeg")},
            timeout=30,
        )
        if upload.status_code == 200 and upload.text.startswith("https://"):
            return upload.text.strip()
    except Exception:
        pass

    return None


_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


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

    # 대표 이미지: og:image → WebP면 JPEG로 교체 시도
    og_image = soup.find("meta", property="og:image")
    image_url = og_image["content"].strip() if og_image and og_image.get("content") else None
    if image_url:
        image_url = _to_jpeg_url(url, image_url)
        if image_url:
            print(f"[DEBUG] 최종 이미지 URL: {image_url}")

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
