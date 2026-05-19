import pytest

from config import settings
from utils.browser_config import (
    LAUNCH_ARGS,
    STEALTH_INIT_SCRIPT,
    browser_context_options,
)


@pytest.fixture(scope="session")
def browser_type_launch_args(browser_type_launch_args):
    return {
        **browser_type_launch_args,
        "headless": settings.HEADLESS,
        "args": [
            *browser_type_launch_args.get("args", []),
            *LAUNCH_ARGS,
        ],
        **({"channel": settings.BROWSER_CHANNEL} if settings.BROWSER_CHANNEL else {}),
    }


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    return {
        **browser_context_args,
        **browser_context_options(),
    }


@pytest.fixture(autouse=True)
def browser_stealth_init(request):
    if "page" not in request.fixturenames:
        return None
    page = request.getfixturevalue("page")
    page.add_init_script(STEALTH_INIT_SCRIPT)
    return None
