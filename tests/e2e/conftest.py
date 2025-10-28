"""E2E test specific fixtures

E2E tests use the full system with real database and services.
"""

import os
import subprocess
import time
from collections.abc import Generator

import httpx
import pytest


@pytest.fixture(scope="session", autouse=True)
def start_test_server() -> Generator[str, None, None]:
    """E2E 테스트 세션 동안 자동으로 서버를 시작하고 종료합니다.

    이 fixture는:
    1. 테스트 시작 전 uvicorn 서버를 백그라운드에서 실행
    2. 헬스체크로 서버 준비 대기
    3. SERVER_URL 환경변수 설정
    4. 모든 E2E 테스트 완료 후 서버 종료

    Yields:
        서버 URL (http://localhost:8000)
    """
    # 서버가 이미 실행 중인지 확인
    server_url = os.getenv("SERVER_URL", "http://localhost:8000")

    try:
        response = httpx.get(f"{server_url}/live", timeout=1.0)
        if response.status_code == 200:
            print(f"✓ Server already running at {server_url}")
            yield server_url
            return
    except (httpx.ConnectError, httpx.TimeoutException):
        pass

    # 서버 시작
    print(f"\n{'='*80}")
    print(f"Starting test server at {server_url}")
    print(f"{'='*80}\n")

    # Uvicorn 프로세스 시작
    server_process = subprocess.Popen(
        [
            "uv", "run", "uvicorn",
            "src.agent_server.main:app",
            "--host", "0.0.0.0",
            "--port", "8000",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    # 서버 준비 대기 (최대 30초)
    max_wait = 30
    start_time = time.time()
    server_ready = False

    while time.time() - start_time < max_wait:
        try:
            response = httpx.get(f"{server_url}/live", timeout=2.0)
            if response.status_code == 200:
                server_ready = True
                print(f"✓ Server is ready at {server_url}")
                break
        except (httpx.ConnectError, httpx.TimeoutException):
            pass

        # 서버 프로세스가 종료되었는지 확인
        if server_process.poll() is not None:
            stdout, stderr = server_process.communicate()
            print("✗ Server process terminated unexpectedly")
            print(f"STDOUT: {stdout}")
            print(f"STDERR: {stderr}")
            pytest.fail("Server failed to start")

        time.sleep(0.5)

    if not server_ready:
        server_process.terminate()
        server_process.wait(timeout=5)
        pytest.fail(f"Server did not become ready within {max_wait} seconds")

    # 환경변수 설정
    os.environ["SERVER_URL"] = server_url

    try:
        yield server_url
    finally:
        # 서버 종료
        print(f"\n{'='*80}")
        print("Shutting down test server")
        print(f"{'='*80}\n")

        server_process.terminate()
        try:
            server_process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server_process.kill()
            server_process.wait()

        print("✓ Server stopped")


@pytest.fixture(scope="session")
def server_url(start_test_server: str) -> str:
    """서버 URL을 반환하는 fixture

    테스트에서 명시적으로 서버 URL이 필요한 경우 사용할 수 있습니다.

    Returns:
        서버 URL (http://localhost:8000)
    """
    return start_test_server
