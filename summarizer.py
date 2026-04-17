"""
Gemini API를 사용해 블로그 글을 인스타그램용 캡션으로 변환합니다.
"""
import os
import google.genai as genai
from dotenv import load_dotenv

load_dotenv()

CAPTION_MAX_LENGTH = int(os.getenv("CAPTION_MAX_LENGTH", "2000"))
BLOG_LINK_TEXT = os.getenv("BLOG_LINK_TEXT", "더 많은 콘텐츠 정보는? @bodyandwell 을 팔로우 해주세요💚")

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

    prompt = f"""다음 블로그 글을 인스타그램용 캡션과 해시태그로 작성해주세요.

[캡션 조건]
- 한국어로 작성
- 핵심 내용을 자연스럽고 친근한 말투로 요약
- 독자가 블로그 본문을 읽고 싶게 흥미를 유발
- 이모지 2~4개 적절히 사용
- 줄바꿈으로 가독성 확보
- {body_max}자 이내
- 블로그 URL은 포함하지 말 것

[해시태그 조건]
- 건강 블로그 계정용
- 글 내용과 직접 관련된 구체적인 태그 3개
- 건강 블로그 공통 태그 1개 (예: #건강 #건강정보 #건강관리 중 가장 적합한 것 1개)
- 총 4개 해시태그
- #기호 포함해서 공백으로 구분
- 한국어 태그 위주, 영어 태그 1~2개 허용

[블로그 제목]
{title}

[블로그 본문]
{content}

아래 형식으로만 출력하세요. 부가 설명 없이.

===CAPTION===
(캡션 텍스트)
===HASHTAGS===
(해시태그)"""

    client = _get_client()
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
            break
        except Exception as e:
            err_str = str(e)
            if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                import re
                delay_match = re.search(r"retryDelay.*?(\d+)s", err_str)
                wait = int(delay_match.group(1)) if delay_match else 60
                if attempt < max_retries - 1:
                    import time as _time
                    _time.sleep(wait + 1)
                    continue
            elif "503" in err_str or "UNAVAILABLE" in err_str:
                if attempt < max_retries - 1:
                    import time as _time
                    _time.sleep(10 * (attempt + 1))  # 10s, 20s
                    continue
            raise
    output = response.text.strip()

    if "===CAPTION===" in output and "===HASHTAGS===" in output:
        parts = output.split("===HASHTAGS===")
        body = parts[0].replace("===CAPTION===", "").strip()
        hashtags = parts[1].strip()
    else:
        # 파싱 실패 시 전체를 캡션으로, 해시태그는 빈 값
        body = output
        hashtags = ""

    # 글자수 초과 시 자르기
    if len(body) > body_max:
        body = body[:body_max - 3] + "..."

    footer = f"\n\n{BLOG_LINK_TEXT}\n\n{hashtags}"
    return f"{body}{footer}"
