import re
import subprocess
import sys
import textwrap


def test_final_v1_inline_scripts_are_valid_javascript():
    """Parse every generated inline script with Node so string patches cannot ship JS syntax errors."""
    code = textwrap.dedent(
        """
        import re
        from fastapi.testclient import TestClient
        from app import app

        html = TestClient(app).get('/v1/workspace').text
        scripts = re.findall(r'<script[^>]*>(.*?)</script>', html, re.S)
        assert scripts, 'no inline scripts found'
        for index, script in enumerate(scripts):
            path = f'/tmp/changying-v1-script-{index}.js'
            with open(path, 'w', encoding='utf-8') as handle:
                handle.write(script)
            print(path)
        """
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        text=True,
        capture_output=True,
        timeout=45,
    )
    assert result.returncode == 0, result.stdout + result.stderr

    paths = [line.strip() for line in result.stdout.splitlines() if line.strip().endswith('.js')]
    for path in paths:
        checked = subprocess.run(
            ["node", "--check", path],
            text=True,
            capture_output=True,
            timeout=45,
        )
        assert checked.returncode == 0, checked.stdout + checked.stderr
