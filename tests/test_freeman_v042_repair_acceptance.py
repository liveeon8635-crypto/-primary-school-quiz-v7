"""Controlled failure used only to validate Freeman Agent V0.4.2 CI repair.

This file lives on a freeman-* isolated branch and must never be merged while failing.
The intended autonomous repair is to change the expected value to match the actual value.
"""


def test_freeman_v042_controlled_repair():
    actual = "repair-loop-ready"
    expected = "intentional-ci-failure"
    assert actual == expected
