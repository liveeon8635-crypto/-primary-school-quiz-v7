"""Regression test for feedback #304: grade 5 PEP curriculum revision.

The teacher reported that the grade 5 knowledge-module practice still used
outdated PEP modules ("简易方程" and "位置") that were revised in the latest
textbook line. This test locks in the curriculum revision marker so the
practice layer can be re-verified against the current PEP edition.
"""

from changying.services.builtin_question_bank_chinese import (
    PEP_G5_CURRICULUM_REVISION,
    PEP_G5_REVISED_MATH_MODULES,
)


def test_pep_g5_curriculum_revision_marker_present():
    assert PEP_G5_CURRICULUM_REVISION
    assert isinstance(PEP_G5_CURRICULUM_REVISION, str)


def test_revised_math_modules_include_feedback_targets():
    assert "简易方程" in PEP_G5_REVISED_MATH_MODULES
    assert "位置" in PEP_G5_REVISED_MATH_MODULES
