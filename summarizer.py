"""
Gemini API를 사용해 블로그 글을 인스타그램용 캡션으로 변환합니다.
"""
import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

CAPTION_MAX_LENGTH = int(os.getenv("CAPTION_MAX_LENGTH", "2000"))
HASHTAGS = os.getenv("HASHTAGS", "#블로그 #정보공유")
BLOG_LINK_TEXT = os.getenv("BLOG_LINK_TEXT", "🔗 블로그 링크는 프로필 바이오에!")

_model = None


def _get_model():
    global _model
    if _model is None:
        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
        _model = genai.GenerativeModel("gemini-2.5-flash")
    return _model


def generate_instagram_caption(post: dict) -> str:
    """
    블로그 글을 인스타그램 캡션으로 요약합니다.

    Args:
        post: parse_post()가 반환한 딕셔너리

    Returns:
        완성된 인스타그램 캡션 문자열
    """
    title = post["title"]
    content = post["plain_text"][:3000]  # 토큰 절약을 위해 앞부분만 사용
    url = post["url"]

    # 해시태그와 링크 안내 문구를 제외한 본문 캡션 최대 길이
    footer = f"\n\n{BLOG_LINK_TEXT}\n{HASHTAGS}"
    body_max = CAPTION_MAX_LENGTH - len(footer)

    prompt = f"""다음 블로그 글을 인스타그램 캡션으로 작성해주세요.

[조건]
- 한국어로 작성
- 핵심 내용을 자연스럽고 친근한 말투로 요약
- 독자가 블로그 본문을 읽고 싶게 흥미를 유발
- 이모지 2~4개 적절히 사용
- 줄바꿈으로 가독성 확보
- {body_max}자 이내 (해시태그 제외)
- 해시태그는 포함하지 말 것 (별도로 추가됨)
- 블로그 URL은 포함하지 말 것 (별도로 안내됨)

[블로그 제목]
{title}

[블로그 본문]
{content}

캡션 텍스트만 출력하세요. 부가 설명 없이."""

    response = _get_model().generate_content(prompt)
    body = response.text.strip()

    # 글자수 초과 시 자르기
    if len(body) > body_max:
        body = body[:body_max - 3] + "..."

    return f"{body}{footer}"
