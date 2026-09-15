"""V0.4.3 受控红灯修复验收测试。

本文件用于验证受控红灯修复循环：
- 初始状态包含一个确定性失败断言，确保第一次真实 CI 失败。
- 修复后 expected 与 actual 一致，CI 转绿。

该测试不依赖生产代码、workflow 或外部依赖，仅验证修复循环本身。
"""

from __future__ import annotations


def test_repair_loop_ready_marker():
    """受控红灯修复循环就绪标记。

    初始红灯阶段：actual="repair-loop-ready"，expected="intentional-ci-failure"，
    断言失败以触发第一次真实 CI 失败。

    修复阶段：将 expected 最小修复为 "repair-loop-ready"，断言通过。
    """
    actual = "repair-loop-ready"
    expected = "intentional-ci-failure"
    assert actual == expected
