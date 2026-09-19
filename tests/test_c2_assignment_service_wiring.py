from __future__ import annotations

import app_v924 as legacy

from app import app  # noqa: F401
from changying.services.assignments import AssignmentService


def test_assignment_read_service_is_installed_into_legacy_runtime():
    service = legacy.assignment_service

    assert isinstance(service, AssignmentService)
    assert legacy.assignment_submission_setting.__self__ is service
    assert legacy.assignment_submission_mode.__self__ is service
    assert legacy.homework_media_count.__self__ is service
    assert legacy.assignment_effective_status.__self__ is service


def test_assignment_service_keeps_existing_submission_mode_contract():
    service = legacy.assignment_service

    assert service.assignment_mode_name("quiz") == "在线答题"
    assert service.assignment_mode_name("media") == "拍照/视频"
    assert service.assignment_mode_name("mixed") == "在线答题 + 拍照/视频"
    assert service.assignment_mode_name("unknown") == "在线答题"
