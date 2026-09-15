from pathlib import Path


def test_classic_login_uses_tutoring_product_identity():
    source = (Path(__file__).resolve().parents[1] / "app_v924.py").read_text(encoding="utf-8")

    assert "V10.7 商业稳定运营版 S1" not in source
    assert 'RELEASE_NAME="小学教学版"' in source
    assert "返回长缨辅学 V1" in source
    assert "长缨辅学教学系统：作业、错题与学习反馈继续沿用现有功能。" in source
