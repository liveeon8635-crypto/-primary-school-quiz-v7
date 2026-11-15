"""Chromium checks using HTML returned by the normal application routes."""

import shutil
import subprocess

import pytest
from fastapi.testclient import TestClient

from app import app


def render_dom(tmp_path, html, size, query=""):
    chrome = shutil.which("google-chrome") or shutil.which("chromium")
    if not chrome:
        pytest.skip("Chrome unavailable on this host")
    page = tmp_path / "acceptance.html"
    page.write_text(html, encoding="utf-8")
    result = subprocess.run(
        [
            chrome,
            "--headless",
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-background-networking",
            f"--user-data-dir={tmp_path / 'chrome'}",
            f"--window-size={size}",
            "--virtual-time-budget=5000",
            "--dump-dom",
            page.as_uri() + query,
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=40,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout


@pytest.mark.parametrize(("width", "height"), [(390, 844), (768, 1024), (1440, 900)])
def test_login_labels_focus_and_width_in_chrome(tmp_path, width, height):
    with TestClient(app) as client:
        response = client.get("/v1")
    assert response.status_code == 200
    html = response.text
    script = """
    const watch = setInterval(() => {
      const user = document.querySelector('#cyLoginUsername');
      const password = document.querySelector('#cyLoginPassword');
      if (!user || !password) return;
      clearInterval(watch);
      user.focus();
      const box = user.form.getBoundingClientRect();
      if (user.labels.length === 1 && password.labels.length === 1 &&
          document.activeElement === user && getComputedStyle(user).outlineWidth === '2px' &&
          box.left >= 0 && box.right <= innerWidth &&
          document.documentElement.scrollWidth <= innerWidth) {
        window.parent.postMessage({kind: 'login', width: innerWidth, height: innerHeight}, '*');
      }
    }, 40);
    """
    fixture = tmp_path / "login.html"
    fixture.write_text(html.replace("</body>", f"<script>{script}</script></body>"), encoding="utf-8")
    harness = f"""<!doctype html><body>
    <script>
    window.addEventListener('message', event => {{
      const frame = document.querySelector('iframe');
      if (event.source === frame.contentWindow && event.data.kind === 'login' &&
          event.data.width === {width} && event.data.height === {height}) {{
        document.body.dataset.browserAcceptance = 'login';
      }}
    }});
    </script>
    <iframe src="{fixture.name}" style="width:{width}px;height:{height}px;border:0"></iframe>
    </body>"""
    dom = render_dom(tmp_path, harness, "1920,1200")
    assert 'data-browser-acceptance="login"' in dom


def weekend_board_fixture():
    with TestClient(app) as client:
        response = client.get("/v1/weekend-board")
    assert response.status_code == 200
    html = response.text
    fixture = """
    sessionStorage.setItem('v717Token', 'synthetic-teacher');
    const slide = {
      title: '合成数学课', status: 'running', currentStage: 3, stageName: '例题讲解',
      deck: {index: 0, total: 1}, remainingSeconds: 60,
      content: Array.from({length: 130}, (_, i) => '观察图形变化并说明理由 ' + (i + 1))
    };
    window.fetch = path => Promise.resolve({
      ok: true,
      json: () => Promise.resolve(path === '/session' ? {role: 'teacher'} : slide)
    });
    """
    exercise = """
    let initial;
    const watch = setInterval(() => {
      const region = document.querySelector('[aria-label="课堂投影内容"]');
      if (!region) return;
      if (!initial && region.scrollHeight > region.clientHeight + 80) {
        initial = region;
        region.focus();
        region.scrollTop = 80;
        slide.content.push('补充观察');
      } else if (initial && region !== initial && region.scrollTop === 80 &&
                 document.activeElement === region && getComputedStyle(region).overflowY === 'auto' &&
                 region.textContent.includes('补充观察')) {
        clearInterval(watch);
        document.body.dataset.browserAcceptance = 'board';
      }
    }, 50);
    """
    html = html.replace("<script>", f"<script>{fixture}</script><script>", 1)
    return html.replace("</body>", f"<script>{exercise}</script></body>")


def test_weekend_board_scroll_and_focus_survive_poll_in_chrome(tmp_path):
    dom = render_dom(
        tmp_path,
        weekend_board_fixture(),
        "1920,1080",
        "?s=1",
    )
    assert 'data-browser-acceptance="board"' in dom

@pytest.mark.parametrize(("width", "height"), [(390, 844), (768, 1024), (1440, 900)])
def test_login_labels_focus_and_width_with_playwright(tmp_path, width, height):
    playwright = pytest.importorskip("playwright.sync_api")
    from playwright.sync_api import sync_playwright

    with TestClient(app) as client:
        response = client.get("/v1")
    assert response.status_code == 200

    with sync_playwright() as runtime:
        browser = runtime.chromium.launch(
            executable_path=shutil.which("chromium") or shutil.which("google-chrome"),
            args=["--no-sandbox"],
        )
        try:
            page = browser.new_page(viewport={"width": width, "height": height})
            url = "https://changying.test/v1"
            page.route(url, lambda route: route.fulfill(status=200, content_type="text/html; charset=utf-8", body=response.text))
            page.goto(url, wait_until="domcontentloaded")
            user = page.locator("#cyLoginUsername")
            password = page.locator("#cyLoginPassword")
            assert user.count() == password.count() == 1
            assert user.evaluate("(element) => element.labels.length") == 1
            assert password.evaluate("(element) => element.labels.length") == 1
            user.focus()
            assert page.evaluate("innerWidth") == width
            assert user.evaluate("(element) => getComputedStyle(element).outlineWidth") == "2px"
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            bounds = user.evaluate("(element) => element.form.getBoundingClientRect().toJSON()")
            assert bounds["left"] >= 0 and bounds["right"] <= width
        finally:
            browser.close()



def test_weekend_board_scroll_and_focus_survive_poll_with_playwright():
    playwright = pytest.importorskip("playwright.sync_api")
    html = weekend_board_fixture()
    url = "https://changying.test/v1/weekend-board?s=1"
    with playwright.sync_playwright() as runtime:
        browser = runtime.chromium.launch(
            executable_path=shutil.which("chromium") or shutil.which("google-chrome"),
            args=["--no-sandbox"],
        )
        try:
            page = browser.new_page(viewport={"width": 1920, "height": 1080})
            page.route(url, lambda route: route.fulfill(
                status=200, content_type="text/html; charset=utf-8", body=html,
            ))
            page.goto(url, wait_until="domcontentloaded")
            page.locator('body[data-browser-acceptance="board"]').wait_for(timeout=12000)
        finally:
            browser.close()
