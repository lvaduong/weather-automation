from pages.base_page import BasePage


class FakePage:
    def __init__(self):
        self.default_timeout = None
        self.goto_calls = 0
        self.timeout_waits = []
        self.load_states = []
        self.content = None
        self.url = ""

    def set_default_timeout(self, timeout):
        self.default_timeout = timeout

    def goto(self, url, wait_until):
        self.goto_calls += 1
        if self.goto_calls == 1:
            raise RuntimeError(
                "Page.goto: net::ERR_HTTP2_PROTOCOL_ERROR at https://www.accuweather.com/"
            )
        self.url = url
        return {"url": url, "wait_until": wait_until}

    def wait_for_load_state(self, state, timeout=None):
        self.load_states.append((state, timeout))

    def wait_for_timeout(self, timeout):
        self.timeout_waits.append(timeout)

    def set_content(self, html, wait_until):
        self.content = {"html": html, "wait_until": wait_until}


def test_goto_retries_transient_navigation_errors():
    fake_page = FakePage()
    page = BasePage(fake_page)

    response = page.goto("file:///tmp/weather.html", "open local file")

    assert response["url"] == "file:///tmp/weather.html"
    assert response["wait_until"] == "commit"
    assert fake_page.goto_calls == 2
    assert fake_page.timeout_waits


def test_goto_continues_when_load_states_timeout():
    class SlowLoadPage(FakePage):
        def goto(self, url, wait_until):
            self.goto_calls += 1
            self.url = url
            return {"url": url, "wait_until": wait_until}

        def wait_for_load_state(self, state, timeout=None):
            self.load_states.append((state, timeout))
            raise RuntimeError(f"{state} timed out")

    fake_page = SlowLoadPage()
    page = BasePage(fake_page)

    response = page.goto("https://www.accuweather.com/en/vn/ho-chi-minh-city/353981/weather-forecast/353981")

    assert response["wait_until"] == "commit"
    assert fake_page.goto_calls == 1
    assert [state for state, timeout in fake_page.load_states] == [
        "domcontentloaded",
        "networkidle",
    ]


def test_take_screenshot_uses_short_viewport_capture(tmp_path):
    class ScreenshotPage(FakePage):
        def __init__(self):
            super().__init__()
            self.screenshot_options = None

        def screenshot(self, **kwargs):
            self.screenshot_options = kwargs

    fake_page = ScreenshotPage()
    page = BasePage(fake_page)

    screenshot_path = page.take_screenshot(tmp_path / "failure.png")

    assert screenshot_path.name == "failure.png"
    assert fake_page.screenshot_options["full_page"] is False
    assert fake_page.screenshot_options["timeout"] == 5000


def test_goto_loads_html_fallback_when_browser_navigation_never_commits(monkeypatch):
    class FailingBrowserPage(FakePage):
        def goto(self, url, wait_until):
            self.goto_calls += 1
            raise RuntimeError("Page.goto: Timeout 30000ms exceeded")

    class FakeResponse:
        url = "https://www.accuweather.com/en/test"
        text = "<html><head><title>Weather</title></head><body>Forecast</body></html>"

        def raise_for_status(self):
            pass

    captured_request = {}

    def fake_get(url, **kwargs):
        captured_request["url"] = url
        captured_request["kwargs"] = kwargs
        return FakeResponse()

    monkeypatch.setattr("pages.base_page.requests.get", fake_get)
    fake_page = FailingBrowserPage()
    page = BasePage(fake_page)

    response = page.goto("https://www.accuweather.com/en/test", "open AccuWeather page")

    assert response.url == "https://www.accuweather.com/en/test"
    assert page.current_url == "https://www.accuweather.com/en/test"
    assert captured_request["kwargs"]["verify"] is False
    assert '<base href="https://www.accuweather.com/en/test">' in fake_page.content["html"]


def test_html_fallback_strips_blocking_assets_before_set_content(monkeypatch):
    class FailingBrowserPage(FakePage):
        def goto(self, url, wait_until):
            self.goto_calls += 1
            raise RuntimeError("Page.goto: Timeout 30000ms exceeded")

        def set_content(self, html, wait_until, timeout=None):
            self.content = {"html": html, "wait_until": wait_until, "timeout": timeout}

    class FakeResponse:
        url = "https://www.accuweather.com/en/test"
        text = """
        <html>
          <head>
            <link rel="stylesheet" href="/slow.css">
            <script src="/slow.js"></script>
            <style>body { display: block; }</style>
          </head>
          <body><a class="daily-forecast-card">Sun 5/17 36° /27° 87%</a></body>
        </html>
        """

        def raise_for_status(self):
            pass

    monkeypatch.setattr("pages.base_page.requests.get", lambda url, **kwargs: FakeResponse())
    fake_page = FailingBrowserPage()
    page = BasePage(fake_page)

    page.goto("https://www.accuweather.com/en/test", "open AccuWeather page")

    html = fake_page.content["html"]
    assert "<script" not in html
    assert "<style" not in html
    assert "rel=\"stylesheet\"" not in html
    assert "daily-forecast-card" in html
    assert fake_page.content["timeout"] == 10000
