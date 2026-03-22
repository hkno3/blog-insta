"""
WordPress → Instagram 자동 게시 웹 애플리케이션
실행: python app.py  →  브라우저에서 http://localhost:5000 접속
"""
import json
import os
import threading
from datetime import datetime

from dotenv import load_dotenv, dotenv_values, set_key
from flask import Flask, jsonify, render_template, request

load_dotenv()

app = Flask(__name__)
app.secret_key = os.urandom(24)

ENV_FILE = os.path.join(os.path.dirname(__file__), ".env")

# 백그라운드 작업 상태
_job_status = {"running": False, "log": [], "last_run": None}
_lock = threading.Lock()


def _log(msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    with _lock:
        _job_status["log"].append(line)
        if len(_job_status["log"]) > 200:
            _job_status["log"] = _job_status["log"][-200:]
    print(line)


# ───────────────────────────── 페이지 라우트 ──────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


# ───────────────────────────── API: 설정 ─────────────────────────────────

@app.route("/api/settings", methods=["GET"])
def get_settings():
    """현재 .env 값 반환 (토큰/패스워드는 마스킹)"""
    if not os.path.exists(ENV_FILE):
        return jsonify({})
    values = dotenv_values(ENV_FILE)
    masked = {}
    SENSITIVE = {"INSTAGRAM_ACCESS_TOKEN", "GEMINI_API_KEY", "WP_APP_PASSWORD", "META_APP_SECRET"}
    for k, v in values.items():
        if k in SENSITIVE and v:
            masked[k] = v[:6] + "****" + v[-4:] if len(v) > 10 else "****"
        else:
            masked[k] = v
    return jsonify(masked)


@app.route("/api/settings", methods=["POST"])
def save_settings():
    """설정을 .env 파일에 저장"""
    data = request.json or {}
    # .env 없으면 example에서 복사
    if not os.path.exists(ENV_FILE):
        example = os.path.join(os.path.dirname(__file__), ".env.example")
        if os.path.exists(example):
            import shutil
            shutil.copy(example, ENV_FILE)
        else:
            open(ENV_FILE, "w").close()

    for key, value in data.items():
        if value and "****" not in str(value):  # 마스킹된 값은 덮어쓰지 않음
            set_key(ENV_FILE, key, str(value))

    load_dotenv(override=True)
    return jsonify({"ok": True})


# ───────────────────────────── API: WordPress ────────────────────────────

@app.route("/api/wp/posts")
def get_wp_posts():
    """WordPress 최근 글 목록"""
    try:
        import wordpress_client as wp
        raws = wp.get_recent_posts(count=20)
        posts = [wp.parse_post(r) for r in raws]
        # 이미지 URL 포함
        for i, r in enumerate(raws):
            posts[i]["image_url"] = wp.get_featured_image_url(r)
        return jsonify({"posts": posts})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ───────────────────────────── API: 게시 이력 ────────────────────────────

@app.route("/api/published")
def get_published():
    import tracker
    data = tracker.get_all_published()
    items = [
        {"wp_id": k, **v}
        for k, v in sorted(data.items(), key=lambda x: x[1]["published_at"], reverse=True)
    ]
    return jsonify({"items": items, "total": len(items)})


# ───────────────────────────── API: 수동 게시 ────────────────────────────

@app.route("/api/post/now", methods=["POST"])
def post_now():
    """새 글을 지금 바로 확인하고 게시"""
    if _job_status["running"]:
        return jsonify({"error": "이미 실행 중입니다."}), 409

    def _run():
        with _lock:
            _job_status["running"] = True
            _job_status["log"] = []

        load_dotenv(override=True)
        try:
            import wordpress_client as wp
            import instagram_client as ig
            import tracker
            from summarizer import generate_instagram_caption

            _log("워드프레스 최근 글 확인 중...")
            raws = wp.get_recent_posts(count=10)
            new_posts = [p for p in raws if not tracker.is_published(p["id"])]

            if not new_posts:
                _log("새로 게시할 글이 없습니다.")
                return

            _log(f"새 글 {len(new_posts)}개 발견")
            for raw in new_posts:
                post = wp.parse_post(raw)
                _log(f"처리 중: {post['title']}")

                image_url = wp.get_featured_image_url(raw)
                if not image_url:
                    _log(f"  ⚠ 대표 이미지 없음 - 건너뜀")
                    continue

                _log("  Claude AI 캡션 생성 중...")
                caption = generate_instagram_caption(post)
                _log(f"  캡션 생성 완료 ({len(caption)}자)")

                _log("  Instagram에 게시 중...")
                media_id = ig.post_to_instagram(image_url, caption)
                tracker.mark_published(post["id"], media_id, post["title"])
                _log(f"  ✅ 게시 완료! media_id={media_id}")

            _log("작업 완료")
        except Exception as e:
            _log(f"❌ 오류 발생: {e}")
        finally:
            with _lock:
                _job_status["running"] = False
                _job_status["last_run"] = datetime.now().isoformat()

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    return jsonify({"ok": True, "message": "게시 작업을 시작했습니다."})


@app.route("/api/post/single", methods=["POST"])
def post_single():
    """특정 글 한 개를 수동으로 게시"""
    data = request.json or {}
    wp_post_id = data.get("wp_post_id")
    image_url = data.get("image_url")
    title = data.get("title", "")

    if not wp_post_id or not image_url:
        return jsonify({"error": "wp_post_id와 image_url이 필요합니다."}), 400

    if _job_status["running"]:
        return jsonify({"error": "이미 실행 중입니다."}), 409

    def _run():
        with _lock:
            _job_status["running"] = True
            _job_status["log"] = []

        load_dotenv(override=True)
        try:
            import wordpress_client as wp
            import instagram_client as ig
            import tracker
            from summarizer import generate_instagram_caption

            _log(f"글 가져오는 중: ID={wp_post_id}")
            raws = wp.get_recent_posts(count=50)
            raw = next((r for r in raws if r["id"] == int(wp_post_id)), None)
            if not raw:
                _log("❌ 해당 글을 찾을 수 없습니다.")
                return

            post = wp.parse_post(raw)
            _log("Claude AI 캡션 생성 중...")
            caption = generate_instagram_caption(post)
            _log(f"캡션 생성 완료 ({len(caption)}자)")

            _log("Instagram에 게시 중...")
            media_id = ig.post_to_instagram(image_url, caption)
            tracker.mark_published(post["id"], media_id, post["title"])
            _log(f"✅ 게시 완료! media_id={media_id}")
        except Exception as e:
            _log(f"❌ 오류: {e}")
        finally:
            with _lock:
                _job_status["running"] = False
                _job_status["last_run"] = datetime.now().isoformat()

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    return jsonify({"ok": True})


# ───────────────────────────── API: 로그/상태 ────────────────────────────

@app.route("/api/status")
def get_status():
    with _lock:
        return jsonify({
            "running": _job_status["running"],
            "last_run": _job_status["last_run"],
            "log": _job_status["log"][-50:],
        })


@app.route("/api/tracker/reset", methods=["POST"])
def reset_tracker():
    """failed_posts.json (또는 전체) 초기화"""
    import tracker as tr
    data = request.json or {}
    target = data.get("target", "failed")  # "failed" | "all"

    if target == "all":
        open(tr.TRACKER_FILE, "w").write("{}")
        open(tr.FAILED_FILE, "w").write("{}")
        return jsonify({"ok": True, "message": "published + failed 초기화 완료"})
    else:
        open(tr.FAILED_FILE, "w").write("{}")
        return jsonify({"ok": True, "message": "failed_posts 초기화 완료"})


@app.route("/api/debug/instagram")
def debug_instagram():
    """Instagram 토큰 디버그 - 토큰 상태 및 오류 상세 확인"""
    load_dotenv(override=True)
    import requests as req

    token = os.getenv("INSTAGRAM_ACCESS_TOKEN", "").strip()
    account_id = os.getenv("INSTAGRAM_BUSINESS_ACCOUNT_ID", "").strip()

    info = {
        "token_length": len(token),
        "token_preview": token[:8] + "..." + token[-4:] if len(token) > 12 else "(짧음)",
        "account_id": account_id,
    }

    # graph.instagram.com /me 엔드포인트로 토큰 유효성 확인
    me_resp = req.get(
        "https://graph.instagram.com/v21.0/me",
        params={"access_token": token, "fields": "id,username,name"},
        timeout=10,
    )
    info["me_raw"] = me_resp.json()

    # account_id로 Instagram 계정 조회
    ig_resp = req.get(
        f"https://graph.instagram.com/v21.0/{account_id}",
        params={"access_token": token, "fields": "id,username,name"},
        timeout=10,
    )
    info["ig_raw"] = ig_resp.json()

    return jsonify(info)


@app.route("/api/test")
def test_connections():
    """API 연결 상태 확인"""
    load_dotenv(override=True)
    results = {}

    # WordPress
    try:
        import wordpress_client as wp
        posts = wp.get_recent_posts(count=1)
        results["wordpress"] = {"ok": True, "msg": f"연결 성공 ({len(posts)}개 글 확인)"}
    except Exception as e:
        results["wordpress"] = {"ok": False, "msg": str(e)}

    # Instagram
    try:
        import instagram_client as ig
        info = ig.get_account_info()
        results["instagram"] = {"ok": True, "msg": f"연결 성공 (@{info.get('username', '?')})"}
    except Exception as e:
        results["instagram"] = {"ok": False, "msg": str(e)}

    # Gemini API
    try:
        import google.generativeai as genai
        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
        model = genai.GenerativeModel("gemini-2.5-flash")
        model.generate_content("hi")
        results["gemini"] = {"ok": True, "msg": "연결 성공 (gemini-2.5-flash)"}
    except Exception as e:
        results["gemini"] = {"ok": False, "msg": str(e)}

    return jsonify(results)


# ───────────────────────────── Webhook ───────────────────────────────────

@app.route("/webhook/instagram", methods=["GET"])
def instagram_webhook_verify():
    """Meta Webhook 인증 (GET)"""
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    verify_token = os.getenv("WEBHOOK_VERIFY_TOKEN", "myverifytoken123")
    if mode == "subscribe" and token == verify_token:
        return challenge, 200
    return "Forbidden", 403


@app.route("/webhook/instagram", methods=["POST"])
def instagram_webhook_receive():
    """Meta Webhook 이벤트 수신 (POST)"""
    payload = request.json or {}
    _log(f"[Webhook] 이벤트 수신: {json.dumps(payload)[:200]}")
    return "OK", 200


if __name__ == "__main__":
    print("=" * 50)
    print("  WordPress → Instagram 자동 게시")
    print("  브라우저에서 http://localhost:5000 접속")
    print("=" * 50)
    app.run(debug=False, host="0.0.0.0", port=5000)
