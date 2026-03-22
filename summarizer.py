"""
Gemini API를 사용해 블로그 글을 인스타그램용 캡션으로 변환합니다.
"""
import os
import google.genai as genai
from dotenv import load_dotenv

load_dotenv()

CAPTION_MAX_LENGTH = int(os.getenv("CAPTION_MAX_LENGTH", "2000"))
BLOG_LINK_TEXT = os.getenv("BLOG_LINK_TEXT", "🔗 블로그 링크는 프로필 바이오에!")

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    return _client


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

    # 해시태그와 링크 안내 문구를 제외한 본문 캡션 최대 길이 (여유분 150자 확보)
    body_max = CAPTION_MAX_LENGTH - len(BLOG_LINK_TEXT) - 150

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

    hashtag_prompt = f"""다음 블로그 글에 어울리는 인스타그램 해시태그를 생성해주세요.

[조건]
- 건강 블로그 계정용
- 글 내용과 직접 관련된 구체적인 태그 5~7개
- 건강 블로그 공통 태그 3~5개 (예: #건강 #건강정보 #건강관리)
- 총 10~12개 해시태그
- #기호 포함해서 공백으로 구분
- 한국어 태그 위주, 영어 태그 1~2개 허용

[블로그 제목]
{title}

[블로그 본문 요약]
{content[:500]}

해시태그만 출력하세요. 부가 설명 없이."""

    client = _get_client()
    response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
    body = response.text.strip()

    hashtag_response = client.models.generate_content(model="gemini-2.5-flash", contents=hashtag_prompt)
    hashtags = hashtag_response.text.strip()

    # 글자수 초과 시 자르기
    if len(body) > body_max:
        body = body[:body_max - 3] + "..."

    footer = f"\n\n{BLOG_LINK_TEXT}\n{hashtags}"
    return f"{body}{footer}"
