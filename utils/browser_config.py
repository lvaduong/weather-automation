from __future__ import annotations

from config import settings


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/130.0.0.0 Safari/537.36"
)

LAUNCH_ARGS = [
    "--incognito",
    "--disable-blink-features=AutomationControlled",
    "--disable-http2",
    "--disable-quic",
    "--start-maximized",
    "--window-size=1366,768",
    "--disable-dev-shm-usage",
]

STEALTH_INIT_SCRIPT = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
Object.defineProperty(navigator, 'plugins', {
  get: () => [1, 2, 3, 4, 5],
});
window.chrome = window.chrome || {};
window.chrome.runtime = window.chrome.runtime || {};
const originalQuery = window.navigator.permissions && window.navigator.permissions.query;
if (originalQuery) {
  window.navigator.permissions.query = (parameters) => (
    parameters && parameters.name === 'notifications'
      ? Promise.resolve({ state: Notification.permission })
      : originalQuery(parameters)
  );
}
"""


def browser_launch_options(extra_args: list[str] | None = None) -> dict:
    args = [*LAUNCH_ARGS]
    if extra_args:
        args.extend(extra_args)
    options = {
        "headless": settings.HEADLESS,
        "args": args,
    }
    if settings.BROWSER_CHANNEL:
        options["channel"] = settings.BROWSER_CHANNEL
    return options


def launch_browser(browser_type):
    options = browser_launch_options()
    try:
        return browser_type.launch(**options)
    except Exception:
        if "channel" not in options:
            raise
        fallback_options = {key: value for key, value in options.items() if key != "channel"}
        return browser_type.launch(**fallback_options)


def browser_context_options() -> dict:
    return {
        "ignore_https_errors": True,
        "viewport": {"width": 1366, "height": 768},
        "screen": {"width": 1366, "height": 768},
        "locale": "en-US",
        "timezone_id": "Asia/Bangkok",
        "extra_http_headers": {
            "Accept-Language": "en-US,en;q=0.9",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        },
        "user_agent": USER_AGENT,
    }


def apply_stealth_context(context) -> None:
    context.add_init_script(STEALTH_INIT_SCRIPT)
