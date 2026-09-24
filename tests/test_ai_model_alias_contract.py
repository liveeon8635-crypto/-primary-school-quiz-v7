from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_deepseek_retired_model_aliases_are_normalized_without_db_migration(tmp_path):
    db_path = tmp_path / "deepseek-model-alias.sqlite3"
    script = r'''
import app_v924 as legacy

assert legacy.AI_DEEPSEEK_CURRENT_MODEL == "deepseek-flash"
assert legacy._ai_effective_model(
    "openai_compatible",
    "https://api.deepseek.com",
    "deepseek-v4-flash",
) == "deepseek-flash"
assert legacy._ai_effective_model(
    "openai_compatible",
    "https://api.deepseek.com/v1/",
    "deepseek-v4-flash-vision-exp",
) == "deepseek-flash"

# Do not rewrite arbitrary OpenAI-compatible providers or unknown future models.
assert legacy._ai_effective_model(
    "openai_compatible",
    "https://example.com/v1",
    "deepseek-v4-flash",
) == "deepseek-v4-flash"
assert legacy._ai_effective_model(
    "openai_compatible",
    "https://api.deepseek.com",
    "deepseek-future-model",
) == "deepseek-future-model"
assert legacy._ai_effective_model(
    "openai_responses",
    "https://api.openai.com/v1",
    "gpt-5.6-terra",
) == "gpt-5.6-terra"

effective, legacy_alias = legacy._ai_model_truth(
    "openai_compatible",
    "https://api.deepseek.com",
    "deepseek-v4-flash",
)
assert effective == "deepseek-flash"
assert legacy_alias == "deepseek-v4-flash"

effective, legacy_alias = legacy._ai_model_truth(
    "openai_compatible",
    "https://api.deepseek.com",
    "deepseek-flash",
)
assert effective == "deepseek-flash"
assert legacy_alias == ""
'''

    env = os.environ.copy()
    env.update(
        {
            "DATABASE_URL": f"sqlite:///{db_path}",
            "JWT_SECRET": "test-jwt-secret-0123456789abcdef0123456789abcdef",
            "COMMERCIAL_ADMIN_KEY": "test-commercial-key-012345678901234567890123",
            "ENABLE_DEMO_SEED": "0",
            "PYTHONPATH": str(ROOT),
        }
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=90,
        check=False,
    )
    assert result.returncode == 0, (
        "DeepSeek model alias contract subprocess failed\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )


def test_ai_runtime_and_admin_save_use_effective_model_alias() -> None:
    source = (ROOT / "app_v924.py").read_text(encoding="utf-8")

    assert 'AI_DEEPSEEK_CURRENT_MODEL="deepseek-flash"' in source
    assert '"deepseek-v4-flash":AI_DEEPSEEK_CURRENT_MODEL' in source
    assert '"deepseek-v4-flash-vision-exp":AI_DEEPSEEK_CURRENT_MODEL' in source
    assert 'model=_ai_effective_model(provider,base,configured_model)' in source
    assert 'configured_model=(b.model or "").strip();model=_ai_effective_model(provider,base,configured_model)' in source
    assert '"configuredModel":configured_model' in source
    assert '"legacyModelAlias":legacy_alias' in source
