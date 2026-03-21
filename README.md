# WordPress → Instagram 자동 게시

워드프레스 블로그 새 글을 Claude AI가 요약하여 인스타그램에 자동으로 게시합니다.

## 동작 흐름

```
WordPress REST API → 새 글 감지 → Claude AI 요약 → Instagram Graph API → 게시
```

## 사전 준비

### 1. Instagram 비즈니스 계정 설정

1. 인스타그램 앱 → 프로필 → 설정 → **계정 유형 변경** → 비즈니스 계정으로 전환
2. [Facebook 페이지](https://www.facebook.com/pages/create) 생성
3. 인스타그램 설정 → **계정** → **연결된 계정** → Facebook 페이지 연결

### 2. Meta Developer App 생성

1. [developers.facebook.com](https://developers.facebook.com) 접속
2. **내 앱** → **앱 만들기** → "비즈니스" 유형 선택
3. **Instagram Graph API** 제품 추가
4. 권한 요청:
   - `instagram_basic`
   - `instagram_content_publish`
5. **Graph API Explorer**에서 Long-lived Token 발급

### 3. 필요한 ID/Token 수집

- **Instagram Business Account ID**: Graph API Explorer에서 `me/accounts` 호출 후 연결된 Instagram 계정 ID
- **Long-lived Access Token**: 60일 유효 (매월 `refresh_token.py` 실행으로 갱신)
- **Claude API Key**: [console.anthropic.com](https://console.anthropic.com)

### 4. WordPress 확인

- WordPress REST API는 기본 활성화 상태
- 대표 이미지(Featured Image)를 설정한 글만 게시됩니다 (Instagram은 이미지 필수)

## 설치 및 실행

```bash
# 의존성 설치
pip install -r requirements.txt

# 환경 변수 설정
cp .env.example .env
# .env 파일을 열어 값 입력

# 연결 테스트
python main.py --test

# 한 번 실행 (새 글 확인 & 게시)
python main.py

# 자동 반복 실행 (6시간마다)
python main.py --schedule

# 게시 이력 확인
python main.py --list
```

## Cron 자동화 (서버/Raspberry Pi)

```bash
# 6시간마다 실행
0 */6 * * * cd /path/to/blog-insta && python main.py >> cron.log 2>&1

# 토큰 매월 1일 갱신
0 9 1 * * cd /path/to/blog-insta && python refresh_token.py >> cron.log 2>&1
```

## 파일 구조

```
blog-insta/
├── main.py              # 메인 실행 파일
├── wordpress_client.py  # WordPress REST API 클라이언트
├── instagram_client.py  # Instagram Graph API 클라이언트
├── summarizer.py        # Claude AI 캡션 생성
├── tracker.py           # 중복 게시 방지 (published_posts.json)
├── refresh_token.py     # 토큰 갱신
├── requirements.txt
├── .env.example
└── .gitignore
```

## 주의사항

- Instagram Graph API는 **비즈니스/크리에이터 계정**만 사용 가능
- 게시에는 **공개 접근 가능한 이미지 URL**이 필요 (WordPress 미디어 URL 사용)
- Instagram API 하루 게시 한도: 50개
- Long-lived Token은 **60일**마다 갱신 필요
