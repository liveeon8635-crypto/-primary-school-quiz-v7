"""V0.4.3 受控红灯修复验收测试。

本文件用于验证受控红灯修复闭环：
- 初始状态包含一个确定性失败断言，确保第一次真实 CI 失败。
- 修复后 expected 与 actual 一致，CI 转绿。

该测试不依赖生产代码、workflow 或外部依赖，仅做纯断言。
"""

from __future__ import annotations


def test_repair_loop_ready_marker() -> None:
    """确定性断言：修复后 expected 与 actual 一致，CI 转绿。"""
    actual = "repair-loop-ready"
    expected = "repair-loop-ready"
    assert actual == expected
