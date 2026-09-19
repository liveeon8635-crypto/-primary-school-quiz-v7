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
