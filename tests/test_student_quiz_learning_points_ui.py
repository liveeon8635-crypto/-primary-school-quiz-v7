def test_classic_student_quiz_shows_learning_points_and_locks_final_submit():
    from app import app  # noqa: F401
    import app_v924 as legacy

    html = legacy.INDEX_HTML

    assert 'answers=[],submitting=false' in html
    assert 'if(submitting){answers.pop();return}' in html
    assert 'submitBtn.disabled=true;submitBtn.textContent="正在提交…"' in html
    assert 'catch(e){submitting=false;answers.pop()' in html
    assert '本题 \'+esc(q.learningPoints||1)+\' 学习积分' in html
    assert '本次获得 +' in html
    assert 'learningPointsAwarded' in html
    assert 'learningPointMax' in html
    assert '每答对1题获得1积分' in html


def test_learning_point_backend_contract_remains_visible_to_classic_result_ui():
    from app import app  # noqa: F401
    import app_v924 as legacy

    html = legacy.INDEX_HTML

    assert '/student/assignments/"+aid+"/submit' in html
    assert '/student/practice-submit' in html
    assert 'Number(r.learningPointsAwarded||0)' in html
    assert 'Number(r.learningPointMax||r.total||0)' in html



def test_classic_quiz_filters_blank_metadata_and_supports_nested_rectangle_figures():
    from app import app  # noqa: F401
    import app_v924 as legacy

    html = legacy.INDEX_HTML

    assert 'filter(Boolean).join(" · ")' in html
    assert "esc(q.textbook)+' · '+esc(q.unit)+' · '+esc(q.knowledge)" not in html
    assert 'shape==="nested_rect"||shape==="rectangle_with_inner_rectangle"' in html



def test_student_progress_separates_recent_submission_from_cumulative_mastery():
    from app import app  # noqa: F401
    import app_v924 as legacy

    html = legacy.INDEX_HTML

    assert "latestSubmission" in html
    assert "最近一次作答" in html
    assert "长期累计掌握率" in html
    assert "长期平均分" in html


def test_nested_rectangle_dimensions_are_placed_near_matching_edges():
    from app import app  # noqa: F401
    import app_v924 as legacy

    html = legacy.INDEX_HTML

    assert '外长 '+ " in html
    assert '外宽 '+ " in html
    assert '内长 '+ " in html
    assert '内宽 '+ " in html
    assert 'text-anchor="middle" font-size="11">外长 ' in html
