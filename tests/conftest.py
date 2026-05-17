import pytest

from config import settings


@pytest.fixture(scope="session")
def browser_type_launch_args(browser_type_launch_args):
    return {
        **browser_type_launch_args,
        "headless": settings.HEADLESS,
        "args": [
            *browser_type_launch_args.get("args", []),
            "--incognito",
            "--disable-blink-features=AutomationControlled",
            "--disable-http2",
            "--disable-quic",
            "--start-maximized",
        ],
    }


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    return {
        **browser_context_args,
        "ignore_https_errors": True,
        "no_viewport": True,
        "locale": "en-US",
        "timezone_id": "Asia/Bangkok",
        "extra_http_headers": {
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        },
        "user_agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/130.0.0.0 Safari/537.36"
        ),
    }
