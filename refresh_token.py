"""
Instagram Long-lived Access Token 자동 갱신
- 매 실행 시 토큰을 갱신하고 GitHub Secret을 자동 업데이트합니다.
- GH_PAT 환경변수(repo secrets 쓰기 권한)가 있을 때만 GitHub Secret을 업데이트합니다.
"""
import base64
import logging
import os

import requests
from dotenv import load_dotenv, set_key

import instagram_client as ig

load_dotenv()
log = logging.getLogger(__name__)


def _update_github_secret(new_token: str) -> bool:
    """GitHub Actions Secret을 새 토큰으로 업데이트합니다."""
    gh_pat = os.getenv("GH_PAT", "").strip()
    repo = os.getenv("GITHUB_REPOSITORY", "hkno3/blog-insta").strip()
    if not gh_pat:
        return False

    try:
        from nacl import encoding, public as nacl_public

        headers = {
            "Authorization": f"Bearer {gh_pat}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

        # 레포 공개키 조회
        r = requests.get(
            f"https://api.github.com/repos/{repo}/actions/secrets/public-key",
            headers=headers,
            timeout=15,
        )
        r.raise_for_status()
        key_data = r.json()

        # 토큰 암호화
        pub_key = nacl_public.PublicKey(key_data["key"].encode(), encoding.Base64Encoder())
        sealed = nacl_public.SealedBox(pub_key).encrypt(new_token.encode())
        encrypted_b64 = base64.b64encode(sealed).decode()

        # Secret 업데이트
        r = requests.put(
            f"https://api.github.com/repos/{repo}/actions/secrets/INSTAGRAM_ACCESS_TOKEN",
            headers=headers,
            json={"encrypted_value": encrypted_b64, "key_id": key_data["key_id"]},
            timeout=15,
        )
        r.raise_for_status()
        return True
    except Exception as e:
        log.warning(f"GitHub Secret 업데이트 실패: {e}")
        return False


def refresh_if_needed() -> None:
    """토큰을 갱신하고 GitHub Secret을 업데이트합니다. 실패해도 메인 로직은 계속 진행됩니다."""
    try:
        result = ig.refresh_access_token()
        new_token = result.get("access_token")
        expires_in = result.get("expires_in", 0)
        days = expires_in // 86400

        if not new_token:
            log.warning("토큰 갱신 응답에 access_token이 없습니다.")
            return

        log.info(f"Instagram 토큰 갱신 완료 (유효기간: {days}일)")

        # GitHub Secret 업데이트
        if _update_github_secret(new_token):
            log.info("GitHub Secret(INSTAGRAM_ACCESS_TOKEN) 자동 업데이트 완료")
        else:
            log.info("GH_PAT 없음 — GitHub Secret은 수동 업데이트 필요")

        # 로컬 .env 업데이트 (있을 경우)
        env_file = os.path.join(os.path.dirname(__file__), ".env")
        if os.path.exists(env_file):
            set_key(env_file, "INSTAGRAM_ACCESS_TOKEN", new_token)

    except Exception as e:
        log.warning(f"토큰 갱신 실패 (메인 로직은 계속 진행): {e}")


def main():
    """수동 실행용"""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    print("Instagram 액세스 토큰 갱신 중...")
    try:
        result = ig.refresh_access_token()
        new_token = result.get("access_token")
        days = result.get("expires_in", 0) // 86400
        print(f"✅ 갱신 성공! 새 토큰 유효기간: {days}일")

        if _update_github_secret(new_token):
            print("✅ GitHub Secret 자동 업데이트 완료")
        else:
            print(f"새 토큰: {new_token}")
            print("GH_PAT가 없어 GitHub Secret은 수동 업데이트하세요.")

        env_file = os.path.join(os.path.dirname(__file__), ".env")
        if os.path.exists(env_file):
            set_key(env_file, "INSTAGRAM_ACCESS_TOKEN", new_token)
            print("✅ .env 파일 업데이트 완료")
    except Exception as e:
        print(f"❌ 갱신 실패: {e}")


if __name__ == "__main__":
    main()
