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


@pytest.mark.parametrize("size", ["390,844", "768,1024", "1440,900"])
def test_login_labels_focus_and_width_in_chrome(tmp_path, size):
    with TestClient(app) as client:
        html = client.get("/v1").text
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
        document.body.dataset.browserAcceptance = 'login';
      }
    }, 40);
    """
    dom = render_dom(tmp_path, html.replace("</body>", f"<script>{script}</script></body>"), size)
    assert 'data-browser-acceptance="login"' in dom


def test_weekend_board_scroll_and_focus_survive_poll_in_chrome(tmp_path):
    with TestClient(app) as client:
        html = client.get("/v1/weekend-board").text
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
      } else if (initial && region !== initial) {
        clearInterval(watch);
        if (region.scrollTop === 80 && document.activeElement === region &&
            getComputedStyle(region).overflowY === 'auto' &&
            region.textContent.includes('补充观察')) {
          document.body.dataset.browserAcceptance = 'board';
        }
      }
    }, 50);
    """
    html = html.replace("<script>", f"<script>{fixture}</script><script>", 1)
    dom = render_dom(
        tmp_path,
        html.replace("</body>", f"<script>{exercise}</script></body>"),
        "1920,1080",
        "?s=1",
    )
    assert 'data-browser-acceptance="board"' in dom
