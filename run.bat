@echo off
chcp 65001 >nul
echo ============================================
echo  WordPress to Instagram 자동 게시 웹앱
echo ============================================
echo.

:: Python 확인
python --version >nul 2>&1
if errorlevel 1 (
    echo [오류] Python이 설치되어 있지 않습니다.
    echo Python 3.11 이상을 설치해주세요: https://www.python.org/downloads/
    pause
    exit /b 1
)

:: 가상환경 생성 (처음 실행 시)
if not exist ".venv" (
    echo [설정] 가상환경 생성 중...
    python -m venv .venv
)

:: 가상환경 활성화
call .venv\Scripts\activate.bat

:: 패키지 설치
echo [설정] 필요한 패키지 설치 중...
pip install -r requirements.txt -q

:: .env 파일 확인
if not exist ".env" (
    echo.
    echo [안내] .env 파일이 없습니다. .env.example을 복사합니다.
    copy .env.example .env >nul
    echo       .env 파일을 메모장으로 열어 API 키를 입력한 후 다시 실행하세요.
    echo.
    start notepad .env
    pause
    exit /b 0
)

:: 브라우저 자동 열기 (2초 후)
echo.
echo [시작] 웹 서버 시작 중...
echo       브라우저에서 http://localhost:5000 이 자동으로 열립니다.
echo       종료하려면 이 창을 닫거나 Ctrl+C 를 누르세요.
echo.
start /b "" timeout /t 2 /nobreak >nul ^& start http://localhost:5000

:: 앱 실행
python app.py

pause
