"""
Instagram Long-lived Access Token 갱신 스크립트
토큰은 60일 유효하며, 만료 30일 전부터 갱신 가능합니다.
이 스크립트를 월 1회 실행하거나 cron에 등록하세요.
"""
import os
from dotenv import load_dotenv, set_key
import instagram_client as ig

load_dotenv()

def main():
    print("Instagram 액세스 토큰 갱신 중...")
    try:
        result = ig.refresh_access_token()
        new_token = result.get("access_token")
        expires_in = result.get("expires_in", 0)
        days = expires_in // 86400

        print(f"✅ 갱신 성공! 새 토큰 유효기간: {days}일")

        # .env 파일 자동 업데이트
        env_file = os.path.join(os.path.dirname(__file__), ".env")
        if os.path.exists(env_file):
            set_key(env_file, "INSTAGRAM_ACCESS_TOKEN", new_token)
            print("✅ .env 파일 업데이트 완료")
        else:
            print(f"새 토큰: {new_token}")
            print(".env 파일에 INSTAGRAM_ACCESS_TOKEN을 위 값으로 수동 업데이트하세요.")
    except Exception as e:
        print(f"❌ 갱신 실패: {e}")
        print("Meta Developer Console에서 수동으로 토큰을 갱신하세요.")
        print("https://developers.facebook.com/tools/explorer/")

if __name__ == "__main__":
    main()
