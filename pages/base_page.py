from __future__ import annotations

import re
from pathlib import Path
from typing import Callable, TypeVar
from urllib.parse import urlsplit

import requests
from config import settings
from utils.logger import get_logger


T = TypeVar("T")


class BasePage:
    def __init__(self, page):
        self.page = page
        self.logger = get_logger(self.__class__.__name__)
        self.current_url = getattr(page, "url", "")
        self.loaded_via_http_fallback = False
        self.page.set_default_timeout(settings.DEFAULT_TIMEOUT_MS)

    def wait_for_page_loaded(self) -> None:
        try:
            self.page.wait_for_load_state("domcontentloaded", timeout=settings.PAGE_LOAD_TIMEOUT_MS)
        except Exception:
            self.logger.info("DOM content load timed out; continuing with committed document")
        try:
            self.page.wait_for_load_state("networkidle", timeout=settings.PAGE_LOAD_TIMEOUT_MS)
        except Exception:
            self.logger.info("Network did not become idle; continuing after page load wait")

    def take_screenshot(self, path: str | Path) -> Path:
        screenshot_path = Path(path)
        screenshot_path.parent.mkdir(parents=True, exist_ok=True)
        self.page.screenshot(
            path=str(screenshot_path),
            full_page=False,
            timeout=settings.SCREENSHOT_TIMEOUT_MS,
        )
        return screenshot_path

    def goto(self, url: str, action_name: str = "navigate"):
        def action():
            try:
                response = self.page.goto(url, wait_until="commit")
                self.current_url = getattr(self.page, "url", url)
                self.loaded_via_http_fallback = False
                self.wait_for_page_loaded()
                return response
            except Exception as browser_error:
                if settings.STRICT_AUTOMATION_FAILURES or not self._can_fallback_to_http(url):
                    raise
                self.logger.warning(
                    "Browser navigation did not commit; loading HTML over HTTP fallback: %s",
                    browser_error,
                )
                return self._goto_via_http_fallback(url)

        return self.retry(action, action_name)

    def _goto_via_http_fallback(self, url: str):
        self._recover_static_fallback_page()
        response = requests.get(
            url,
            timeout=settings.DEFAULT_TIMEOUT_MS / 1000,
            verify=False,
            headers={
                "Accept-Language": "en-US,en;q=0.9",
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/130.0.0.0 Safari/537.36"
                ),
            },
        )
        response.raise_for_status()
        self._set_static_fallback_content(response.text, url)
        self.current_url = response.url
        self.loaded_via_http_fallback = True
        self.wait_for_page_loaded()
        return response

    def _set_static_fallback_content(self, html: str, url: str) -> None:
        fallback_html = self._html_with_base_url(self._strip_blocking_assets(html), url)
        try:
            self.page.set_content(
                fallback_html,
                wait_until="domcontentloaded",
                timeout=settings.PAGE_LOAD_TIMEOUT_MS,
            )
        except TypeError:
            self.page.set_content(fallback_html, wait_until="domcontentloaded")

    def _recover_static_fallback_page(self) -> None:
        context = getattr(self.page, "context", None)
        if context is not None:
            try:
                fresh_page = context.new_page()
                fresh_page.set_default_timeout(settings.DEFAULT_TIMEOUT_MS)
                try:
                    self.page.close()
                except Exception:
                    pass
                self.page = fresh_page
                self.current_url = getattr(fresh_page, "url", "")
                return
            except Exception as new_page_error:
                self.logger.info("Could not create fresh page for HTTP fallback: %s", new_page_error)

        try:
            self.page.evaluate("window.stop()")
            return
        except Exception as stop_error:
            self.logger.info("Could not stop stalled page before HTTP fallback: %s", stop_error)

    @staticmethod
    def _can_fallback_to_http(url: str) -> bool:
        return urlsplit(url).scheme in {"http", "https"}

    @staticmethod
    def _html_with_base_url(html: str, url: str) -> str:
        base_tag = f'<base href="{url}">'
        head_match = html.lower().find("<head")
        if head_match == -1:
            return f"{base_tag}\n{html}"

        head_end = html.find(">", head_match)
        if head_end == -1:
            return f"{base_tag}\n{html}"
        return f"{html[:head_end + 1]}\n{base_tag}\n{html[head_end + 1:]}"

    @staticmethod
    def _strip_blocking_assets(html: str) -> str:
        html = re.sub(r"<script\b[^>]*>.*?</script>", "", html, flags=re.I | re.S)
        html = re.sub(r"<style\b[^>]*>.*?</style>", "", html, flags=re.I | re.S)
        html = re.sub(r"<link\b[^>]*rel=[\"']?(?:stylesheet|preload|preconnect)[^>]*>", "", html, flags=re.I)
        html = re.sub(
            r"<(?:iframe|object|embed|picture|video|audio)\b[^>]*>.*?"
            r"</(?:iframe|object|embed|picture|video|audio)>",
            "",
            html,
            flags=re.I | re.S,
        )
        html = re.sub(r"<(?:img|source)\b[^>]*>", "", html, flags=re.I)
        return html

    def retry(self, action: Callable[[], T], action_name: str) -> T:
        last_error: Exception | None = None
        for attempt in range(1, settings.RETRY_ATTEMPTS + 1):
            try:
                return action()
            except Exception as error:
                last_error = error
                self.logger.warning("%s failed on attempt %s: %s", action_name, attempt, error)
                if attempt < settings.RETRY_ATTEMPTS:
                    self.page.wait_for_timeout(settings.RETRY_DELAY_MS)
        raise RuntimeError(f"{action_name} failed after {settings.RETRY_ATTEMPTS} attempts") from last_error
