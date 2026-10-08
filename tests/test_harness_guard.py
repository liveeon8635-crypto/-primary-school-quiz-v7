from scripts.harness_guard import evaluate, is_c2_read_side, is_secret_path


def test_c2_read_side_detection_requires_branch_and_read_marker():
    assert is_c2_read_side(
        "refactor/c2-wrong-question-reads",
        "refactor(C2): 错题纯读取迁入服务层",
        "只处理读侧",
    )
    assert not is_c2_read_side("feature/ui", "纯读取", "读侧")
    assert not is_c2_read_side("refactor/c2-write-points", "积分写入", "write side")


def test_secret_like_files_are_always_blocked():
    assert is_secret_path(".env")
    assert is_secret_path("config/.env.production")
    assert is_secret_path("keys/server.pem")
    assert is_secret_path("id_rsa")

    errors = evaluate(
        [".env"],
        [],
        branch="feature/ui",
        title="normal change",
        body="",
    )
    assert errors


def test_c2_read_side_blocks_production_config_and_write_lines():
    errors = evaluate(
        ["app.py", "app_v924.py"],
        [
            ("app_v924.py", "db.commit()"),
            ("app_v924.py", '@app.post("/teacher/write")'),
        ],
        branch="refactor/c2-example",
        title="refactor(C2): read-side service",
        body="纯读取迁移",
    )

    assert any("high-risk path" in error for error in errors)
    assert any("db.commit" in error for error in errors)
    assert any("@app.post" in error for error in errors)


def test_c2_read_side_allows_service_reads_and_test_writes():
    errors = evaluate(
        [
            "app_v924.py",
            "changying/services/example.py",
            "tests/test_example.py",
        ],
        [
            ("app_v924.py", "rows=example_service.rows(db,school_id=u.school_id)"),
            ("changying/services/example.py", "return list(db.scalars(query).all())"),
        ],
        branch="refactor/c2-example-reads",
        title="refactor(C2): 将查询读侧迁入服务层",
        body="pure read-side",
    )

    assert errors == []


def _wiring(old: dict, new: dict, changed: list[str]):
    from scripts.harness_guard import find_unwired_symbols

    return find_unwired_symbols(
        changed,
        lambda p: new.get(p, ""),
        lambda p: old.get(p, ""),
        list(new),
    )


def test_wiring_flags_new_helper_nothing_calls():
    old = {"changying/a.py": "def existing():\n    return 1\n"}
    new = {
        "changying/a.py": "def existing():\n    return 1\n\n\ndef paper_import_allows_pdf(name):\n    return name.endswith('.pdf')\n",
        "tests/test_a.py": "from changying.a import paper_import_allows_pdf\n",
    }
    problems = _wiring(old, new, ["changying/a.py"])
    assert any("paper_import_allows_pdf" in item for item in problems)


def test_wiring_flags_unused_constant_and_route_registrar():
    old = {"changying/a.py": "X = 1\n"}
    new = {
        "changying/a.py": "X = 1\nPAPER_IMPORT_PDF_ENABLED = True\n\n\ndef register_upload_routes(app):\n    return app\n",
    }
    problems = _wiring(old, new, ["changying/a.py"])
    assert any("PAPER_IMPORT_PDF_ENABLED" in item for item in problems)
    assert any("register_upload_routes" in item for item in problems)


def test_wiring_accepts_symbols_used_by_runtime_code_or_routes():
    old = {"changying/a.py": "X = 1\n", "changying/b.py": "def old():\n    return 1\n"}
    new = {
        "changying/a.py": "X = 1\n\n\ndef helper():\n    return 2\n\n\n@router.get('/x')\ndef handler():\n    return 3\n",
        "changying/b.py": "from changying.a import helper\n\n\ndef old():\n    return helper()\n",
    }
    assert _wiring(old, new, ["changying/a.py", "changying/b.py"]) == []


def test_wiring_ignores_tests_scripts_and_existing_symbols():
    old = {"changying/a.py": "def keep():\n    return 1\n"}
    new = {
        "changying/a.py": "def keep():\n    return 1\n",
        "tests/test_x.py": "def helper_only_for_tests():\n    return 1\n",
        "scripts/tool.py": "def tool():\n    return 1\n",
    }
    assert _wiring(old, new, ["changying/a.py", "tests/test_x.py", "scripts/tool.py"]) == []
