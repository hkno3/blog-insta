"""
WordPress → Instagram 자동 게시 메인 스크립트

사용법:
  # 한 번 실행 (새 글 확인 후 게시):
  python main.py

  # 연결 상태 테스트:
  python main.py --test

  # 게시 이력 확인:
  python main.py --list
"""
import argparse
import logging
import os
import sys
from dotenv import load_dotenv

import tracker
import wordpress_client as wp
import instagram_client as ig
from summarizer import generate_instagram_caption
import sheets_client
from scraper import scrape_post

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("blog_insta.log", encoding="utf-8"),
    ],
)
log = logging.getLogger(__name__)


def run_once() -> None:
    """새 워드프레스 글을 확인하고 인스타그램에 게시합니다."""
    log.info("워드프레스 최근 글 확인 중...")
    try:
        raw_posts = wp.get_recent_posts(count=100)
    except Exception as e:
        log.error(f"워드프레스 API 호출 실패: {e}")
        return

    if not isinstance(raw_posts, list):
        log.error(f"워드프레스 API 응답 형식 오류: {type(raw_posts).__name__} — {str(raw_posts)[:200]}")
        return

    new_posts = [p for p in raw_posts if not tracker.is_published(p["id"]) and not tracker.is_failed(p["id"])]
    if not new_posts:
        log.info("새로 게시할 글이 없습니다.")
        return

    # 오래된 글부터 순서대로 시도, 성공하면 바로 종료
    candidates = list(reversed(new_posts))  # 오래된 글부터
    log.info(f"미게시 글 {len(candidates)}개 중 1개 업로드 시도")

    for raw in candidates:
        post = wp.parse_post(raw)
        log.info(f"처리 중: [{post['id']}] {post['title']}")

        # 대표 이미지 가져오기
        image_url = wp.get_featured_image_url(raw)
        if not image_url:
            log.warning(f"대표 이미지 없음 - 스킵: {post['title']}")
            tracker.mark_failed(post["id"], post["title"], "대표 이미지 없음")
            continue

        # Claude로 캡션 생성
        try:
            caption = generate_instagram_caption(post)
            log.info(f"캡션 생성 완료 ({len(caption)}자)")
        except Exception as e:
            err_str = str(e)
            if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                log.warning(f"Gemini API 한도 초과 - 다음 실행에 재시도: {post['title']}")
                break  # 한도 소진 시 더 시도해도 소용없으므로 루프 종료
            log.error(f"캡션 생성 실패 - 스킵: {e}")
            tracker.mark_failed(post["id"], post["title"], f"캡션 생성 실패: {e}")
            continue

        # 인스타그램 게시
        try:
            media_id = ig.post_to_instagram(image_url, caption)
            tracker.mark_published(post["id"], media_id, post["title"])
            log.info(f"인스타그램 게시 완료! media_id={media_id}")
            log.info(f"  제목: {post['title']}")
            log.info(f"  원문: {post['url']}")
            return  # 1개 성공하면 종료, 1시간 뒤 다시 실행
        except Exception as e:
            log.error(f"인스타그램 게시 실패 - 다음 글 시도: {e}")
            tracker.mark_failed(post["id"], post["title"], f"Instagram API 오류: {e}")
            continue

    log.warning("모든 미게시 글 게시 실패. failed_posts.json 확인 필요.")




def run_once_from_sheets() -> None:
    """구글 시트 URL 목록을 읽어 미게시 글 1개를 인스타그램에 게시합니다."""
    log.info("구글 시트에서 URL 목록 가져오는 중...")
    try:
        urls = sheets_client.get_post_urls()
    except Exception as e:
        log.error(f"구글 시트 접근 실패: {e}")
        return

    if not urls:
        log.info("시트에 URL이 없습니다.")
        return

    # 미게시 + 미실패 URL만 필터링
    candidates = [u for u in urls if not tracker.is_published_url(u) and not tracker.is_failed_url(u)]
    if not candidates:
        log.info("새로 게시할 글이 없습니다.")
        return

    # 오래된 글부터 (시트 순서 = 오래된 순), 최대 20개 시도
    log.info(f"미게시 글 {len(candidates)}개 중 1개 업로드 시도")

    for url in candidates[:20]:
        log.info(f"스크래핑 중: {url}")

        # 페이지 스크래핑
        try:
            post = scrape_post(url)
        except Exception as e:
            log.error(f"스크래핑 실패 - 스킵: {e}")
            tracker.mark_failed_url(url, url, f"스크래핑 실패: {e}")
            continue

        log.info(f"제목: {post['title']}")

        # 대표 이미지 확인
        if not post["image_url"]:
            log.warning(f"og:image 없음 - 스킵: {url}")
            tracker.mark_failed_url(url, post["title"], "og:image 없음")
            continue

        log.info(f"이미지: {post['image_url']}")

        # 캡션 생성
        try:
            caption = generate_instagram_caption(post)
            log.info(f"캡션 생성 완료 ({len(caption)}자)")
        except Exception as e:
            err_str = str(e)
            if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                log.warning(f"Gemini API 한도 초과 - 다음 실행에 재시도: {url}")
                break
            log.error(f"캡션 생성 실패 - 스킵: {e}")
            tracker.mark_failed_url(url, post["title"], f"캡션 생성 실패: {e}")
            continue

        # 인스타그램 게시
        try:
            media_id = ig.post_to_instagram(post["image_url"], caption)
            tracker.mark_published_url(url, media_id, post["title"])
            log.info(f"인스타그램 게시 완료! media_id={media_id}")
            log.info(f"  제목: {post['title']}")
            log.info(f"  원문: {url}")
            return  # 1개 성공 후 종료
        except Exception as e:
            log.error(f"인스타그램 게시 실패 - 다음 글 시도: {e}")
            tracker.mark_failed_url(url, post["title"], f"Instagram API 오류: {e}")
            continue

    log.warning("모든 미게시 글 게시 실패.")


def test_connections() -> None:
    """WordPress, Instagram, Claude API 연결을 테스트합니다."""
    print("\n=== 연결 테스트 ===\n")

    # WordPress
    try:
        posts = wp.get_recent_posts(count=1)
        print(f"✅ WordPress: 연결 성공 (최근 글: {posts[0]['title']['rendered'][:30]}...)")
    except Exception as e:
        print(f"❌ WordPress: 연결 실패 - {e}")

    # Instagram
    try:
        info = ig.get_account_info()
        print(f"✅ Instagram: 연결 성공 (@{info.get('username', 'unknown')})")
    except Exception as e:
        print(f"❌ Instagram: 연결 실패 - {e}")

    # Claude API
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=10,
            messages=[{"role": "user", "content": "ping"}],
        )
        print(f"✅ Claude API: 연결 성공")
    except Exception as e:
        print(f"❌ Claude API: 연결 실패 - {e}")

    print()


def list_published() -> None:
    """게시 이력을 출력합니다."""
    data = tracker.get_all_published()
    if not data:
        print("아직 게시된 글이 없습니다.")
        return
    print(f"\n총 {len(data)}개 게시됨:\n")
    for wp_id, info in sorted(data.items(), key=lambda x: x[1]["published_at"], reverse=True):
        print(f"  WP ID {wp_id}: {info['title']}")
        print(f"    게시일: {info['published_at']}")
        print(f"    IG 미디어: {info['instagram_media_id']}\n")


def main():
    parser = argparse.ArgumentParser(description="WordPress → Instagram 자동 게시")
    parser.add_argument("--test", action="store_true", help="연결 상태 테스트")
    parser.add_argument("--list", action="store_true", help="게시 이력 출력")
    args = parser.parse_args()

    if args.test:
        test_connections()
    elif args.list:
        list_published()
    else:
        run_once_from_sheets()


if __name__ == "__main__":
    main()
