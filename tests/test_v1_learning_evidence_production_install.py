def test_production_loader_installs_learning_evidence_profile_wrapper():
    import app_v924
    from app import app

    assert app is app_v924.app
    assert getattr(app_v924, "_v1_learning_evidence_profile_installed", False) is True
    assert getattr(app_v924, "_v1_parent_link_history_profile_installed", False) is True
    assert callable(app_v924.student_growth_profile_data)


def test_growth_profile_wrapper_keeps_existing_route_contract():
    import app_v924
    from app import app

    paths = {
        route.path
        for route in app.routes
        if hasattr(route, "path")
    }
    assert "/teacher/students/{sid}/growth-profile" in paths
    assert getattr(app_v924, "_v1_learning_evidence_profile_installed", False) is True
