import io
import inspect
import zipfile

import pytest
from fastapi import HTTPException

import app_v924 as legacy


def _tiny_xlsx_shell():
    bio = io.BytesIO()
    with zipfile.ZipFile(bio, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("xl/workbook.xml", "<workbook/>")
    return bio.getvalue()


def test_admin_xlsx_upload_has_pre_decompression_limits():
    legacy._validate_admin_xlsx_upload(_tiny_xlsx_shell())

    with pytest.raises(HTTPException) as exc:
        legacy._validate_admin_xlsx_upload(b"x" * (legacy.ADMIN_IMPORT_MAX_FILE + 1))
    assert exc.value.status_code == 413

    source = inspect.getsource(legacy.import_xlsx)
    assert "file.read(ADMIN_IMPORT_MAX_FILE+1)" in source
    assert "load_workbook(io.BytesIO(data),data_only=True,read_only=True)" in source
    assert "ADMIN_IMPORT_MAX_ROWS_PER_SHEET" in source


def test_teaching_office_upload_has_pre_parse_archive_limits():
    source = inspect.getsource(legacy._validate_office_upload)
    assert "infolist()" in source
    assert "TEACHING_RESOURCE_MAX_ZIP_ENTRIES" in source
    assert "TEACHING_RESOURCE_MAX_UNCOMPRESSED" in source
    assert "Office 文件内部条目过多" in source
    assert "Office 文件解压后内容过大" in source


def test_ai_base_url_rejects_non_global_targets():
    assert legacy._ai_host_is_forbidden("127.0.0.1")
    assert legacy._ai_host_is_forbidden("192.0.2.1")
    assert not legacy._ai_host_is_forbidden("8.8.8.8")

    with pytest.raises(HTTPException):
        legacy._validate_ai_base_url("https://localhost/v1")

    assert legacy._validate_ai_base_url("https://8.8.8.8/v1") == "https://8.8.8.8/v1"


def test_production_ai_base_requires_operator_host_allowlist(monkeypatch):
    monkeypatch.setattr(legacy, "raw_url", "postgresql+psycopg://production")
    monkeypatch.delenv("AI_ALLOWED_HOSTS", raising=False)

    assert legacy._validate_ai_base_url("https://api.openai.com/v1") == "https://api.openai.com/v1"
    assert legacy._validate_ai_base_url("https://api.deepseek.com/v1") == "https://api.deepseek.com/v1"

    with pytest.raises(HTTPException) as exc:
        legacy._validate_ai_base_url("https://customer-controlled.example/v1")
    assert exc.value.status_code == 400
    assert "允许清单" in str(exc.value.detail)

    monkeypatch.setenv("AI_ALLOWED_HOSTS", "api.openrouter.ai")
    assert legacy._validate_ai_base_url("https://api.openrouter.ai/v1") == "https://api.openrouter.ai/v1"


def test_ai_runtime_resolution_rejects_non_global_dns(monkeypatch):
    monkeypatch.setattr(
        legacy.socket,
        "getaddrinfo",
        lambda *args, **kwargs: [(legacy.socket.AF_INET, legacy.socket.SOCK_STREAM, 6, "", ("192.0.2.1", 443))],
    )
    with pytest.raises(HTTPException) as exc:
        legacy._validate_ai_base_url("https://api.example.test/v1", runtime=True)
    assert exc.value.status_code == 502


def test_ai_runtime_resolution_allows_global_dns(monkeypatch):
    monkeypatch.setattr(
        legacy.socket,
        "getaddrinfo",
        lambda *args, **kwargs: [(legacy.socket.AF_INET, legacy.socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443))],
    )
    assert legacy._validate_ai_base_url("https://api.example.test/v1", runtime=True) == "https://api.example.test/v1"


def test_login_rate_tracker_is_bounded_and_legacy_unbounded_map_is_gone():
    assert legacy._login_rate_limiter.max_keys == legacy.LOGIN_RATE_MAX_CLIENTS
    assert legacy.LOGIN_RATE_MAX_CLIENTS <= 65536
    source = inspect.getsource(legacy)
    assert "_login_rate_hits={}" not in source


def test_cors_defaults_to_same_origin_and_wildcard_is_launch_blocker():
    source = inspect.getsource(legacy)
    assert 'os.getenv("CORS_ORIGINS","")' in source
    assert 'CORS_ORIGINS 不得为 *' in source
    assert "connect-src 'self' https:" in source
    assert "connect-src 'self' https: http:" not in source


def test_request_id_is_sanitized_before_reflection():
    source = inspect.getsource(legacy.production_security_headers)
    assert "A-Za-z0-9._:-" in source
    assert "secrets.token_hex(8)" in source
