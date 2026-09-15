from changying.domain.student_continuity import (
    CompletionActor,
    DataDomain,
    IdentityRole,
    MasteryStage,
    StudentRecordRef,
    TeachingCycle,
    TeachingMode,
    TransitionPlan,
    UserIdentity,
)


def test_continuity_contract_keeps_one_student_key_across_cycles():
    record = StudentRecordRef(
        student_id=42,
        current_grade=5,
        active_cycle_ids=("term-2026-spring", "weekend-2026-spring"),
        guardian_ids=(8, 11),
    )

    assert record.student_id == 42
    assert len(record.active_cycle_ids) == 2
    assert len(record.guardian_ids) == 2


def test_v1_contract_reserves_roles_domains_mastery_and_completion_actor():
    assert {x.value for x in IdentityRole} == {
        "school_admin", "school_teacher", "institution_admin",
        "institution_teacher", "parent", "student",
    }
    assert {x.value for x in DataDomain} == {
        "student", "school", "institution", "family", "authorized_share",
    }
    assert [x.value for x in MasteryStage] == ["not_yet", "learning", "basic", "stable"]
    assert CompletionActor.PARENT_ASSISTED.value == "parent_assisted"
    assert TeachingMode.SCHOOL.value == "school"
    assert TeachingCycle.SUMMER.value == "summer"


def test_transition_plan_preserves_full_v1_path():
    plan = TransitionPlan(student_id=42, transition_type="小升初")
    assert plan.student_id == 42
    assert plan.prerequisite_check == []
    assert plan.opening_diagnosis == []


def test_user_identity_is_selectable_without_duplicating_account():
    school = UserIdentity(7, IdentityRole.SCHOOL_TEACHER, "school:1", "学校教师")
    institution = UserIdentity(7, IdentityRole.INSTITUTION_TEACHER, "institution:1", "机构老师")
    assert school.account_id == institution.account_id
    assert school.role != institution.role
