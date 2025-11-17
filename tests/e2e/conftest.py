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
    """Automatically starts and stops the server for the E2E test session.

    This fixture:
    1. Runs the uvicorn server in the background before tests start.
    2. Waits for the server to be ready using a health check.
    3. Sets the SERVER_URL environment variable.
    4. Shuts down the server after all E2E tests are complete.

    Yields:
        The server URL (http://localhost:8000).
    """
    # Check if the server is already running
    server_url = os.getenv("SERVER_URL", "http://localhost:8000")

    try:
        response = httpx.get(f"{server_url}/live", timeout=1.0)
        if response.status_code == 200:
            print(f"✓ Server already running at {server_url}")
            yield server_url
            return
    except (httpx.ConnectError, httpx.TimeoutException):
        pass

    # Start the server
    print(f"\n{'='*80}")
    print(f"Starting test server at {server_url}")
    print(f"{'='*80}\n")

    # Start the Uvicorn process
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

    # Wait for the server to be ready (max 30 seconds)
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

        # Check if the server process has terminated
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

    # Set environment variable
    os.environ["SERVER_URL"] = server_url

    try:
        yield server_url
    finally:
        # Shut down the server
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
    """A fixture that returns the server URL.

    Can be used when tests explicitly need the server URL.

    Returns:
        The server URL (http://localhost:8000).
    """
    return start_test_server
