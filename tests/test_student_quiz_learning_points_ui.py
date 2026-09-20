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
