"""
Google Sheets에서 블로그 URL 목록을 가져옵니다.
공개 시트 CSV export를 사용하므로 API 키 불필요.
"""
import csv
import io
import os

import requests
from dotenv import load_dotenv

load_dotenv()

SHEET_ID = os.getenv("GOOGLE_SHEET_ID", "")


def get_post_urls() -> list[str]:
    """구글 시트 A2~ 에서 포스트 URL 목록을 반환합니다. (A1 도메인 주소 제외)"""
    export_url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"
    resp = requests.get(export_url, timeout=30)
    resp.raise_for_status()

    reader = csv.reader(io.StringIO(resp.text))
    urls = []
    for i, row in enumerate(reader):
        if i == 0:  # A1: 도메인 주소 스킵
            continue
        if i > 49:  # A50까지만 읽기
            break
        if row and row[0].strip().startswith("http"):
            urls.append(row[0].strip())
    return urls
