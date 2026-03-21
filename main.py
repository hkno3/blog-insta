"""
WordPress → Instagram 자동 게시 메인 스크립트

사용법:
  # 한 번 실행 (새 글 확인 후 게시):
  python main.py

  # 주기적 자동 실행 (스케줄러):
  python main.py --schedule

  # 연결 상태 테스트:
  python main.py --test

  # 게시 이력 확인:
  python main.py --list
"""
import argparse
import logging
import os
import sys
import time
import schedule
from dotenv import load_dotenv

import tracker
import wordpress_client as wp
import instagram_client as ig
from summarizer import generate_instagram_caption

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

CHECK_INTERVAL_HOURS = float(os.getenv("CHECK_INTERVAL_HOURS", "1"))


def run_once() -> None:
    """새 워드프레스 글을 확인하고 인스타그램에 게시합니다."""
    log.info("워드프레스 최근 글 확인 중...")
    try:
        raw_posts = wp.get_recent_posts(count=10)
    except Exception as e:
        log.error(f"워드프레스 API 호출 실패: {e}")
        return

    new_posts = [p for p in raw_posts if not tracker.is_published(p["id"])]
    if not new_posts:
        log.info("새로 게시할 글이 없습니다.")
        return

    log.info(f"미게시 글 {len(new_posts)}개 중 1개 업로드")

    # 가장 오래된 미게시 글 1개만 처리
    for raw in new_posts[-1:]:
        post = wp.parse_post(raw)
        log.info(f"처리 중: [{post['id']}] {post['title']}")

        # 대표 이미지 가져오기
        image_url = wp.get_featured_image_url(raw)
        if not image_url:
            log.warning(f"대표 이미지 없음 - 건너뜀: {post['title']}")
            log.warning("  → 워드프레스 글에 대표 이미지를 설정하면 자동으로 사용됩니다.")
            continue

        # Claude로 캡션 생성
        try:
            caption = generate_instagram_caption(post)
            log.info(f"캡션 생성 완료 ({len(caption)}자)")
        except Exception as e:
            log.error(f"캡션 생성 실패: {e}")
            continue

        # 인스타그램 게시
        try:
            media_id = ig.post_to_instagram(image_url, caption)
            tracker.mark_published(post["id"], media_id, post["title"])
            log.info(f"인스타그램 게시 완료! media_id={media_id}")
            log.info(f"  제목: {post['title']}")
            log.info(f"  원문: {post['url']}")
        except Exception as e:
            log.error(f"인스타그램 게시 실패: {e}")



def run_schedule() -> None:
    """주기적으로 run_once()를 실행합니다."""
    log.info(f"스케줄러 시작: {CHECK_INTERVAL_HOURS}시간마다 1개 업로드")
    run_once()  # 시작 즉시 한 번 실행
    schedule.every(CHECK_INTERVAL_HOURS).hours.do(run_once)
    while True:
        schedule.run_pending()
        time.sleep(60)


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
    parser.add_argument("--schedule", action="store_true", help="주기적 자동 실행 모드")
    parser.add_argument("--test", action="store_true", help="연결 상태 테스트")
    parser.add_argument("--list", action="store_true", help="게시 이력 출력")
    args = parser.parse_args()

    if args.test:
        test_connections()
    elif args.list:
        list_published()
    elif args.schedule:
        run_schedule()
    else:
        run_once()


if __name__ == "__main__":
    main()
