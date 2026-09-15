"""V0.4.3 受控红灯修复验收测试。

本文件用于验证受控红灯 -> 最小修复 -> 绿灯的闭环流程。
初始状态故意包含一个确定性失败断言，用于触发第一次真实 CI 失败。
修复后 expected 与 actual 一致，测试通过。
"""


def test_repair_loop_ready_marker():
    actual = "repair-loop-ready"
    expected = "repair-loop-ready"
    assert actual == expected
