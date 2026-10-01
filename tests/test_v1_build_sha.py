from changying.web.v1 import current_v1_build_id, v1_html

def test_v1_build_sha_prefers_render_commit(monkeypatch):
    sha = "a" * 40
    monkeypatch.setenv("RENDER_GIT_COMMIT", sha)
    monkeypatch.setenv("GIT_COMMIT", "b" * 40)
    assert current_v1_build_id() == sha
    assert f'<meta name="build-sha" content="{sha}">' in v1_html()

def test_v1_build_sha_uses_git_commit_fallback_env(monkeypatch):
    monkeypatch.delenv("RENDER_GIT_COMMIT", raising=False)
    monkeypatch.setenv("GIT_COMMIT", "c" * 40)
    assert current_v1_build_id() == "c" * 40
