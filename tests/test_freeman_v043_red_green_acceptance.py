"""V0.4.3 受控红灯修复验收测试。

本文件用于验证受控红灯 -> 修复 -> 绿灯的闭环流程：
初始提交包含一个确定性失败断言，CI 首次运行必然失败；
随后仅修改本文件中的 expected 值，使断言通过，CI 转为绿灯。

该测试不依赖生产代码、workflow 或外部依赖，仅做纯字符串断言。
"""

from __future__ import annotations


def test_repair_loop_ready_marker() -> None:
    """受控红灯断言：初始 expected 故意与 actual 不一致。"""
    actual = "repair-loop-ready"
    expected = "intentional-ci-failure"
    assert actual == expected
