-- 正式使用前清理测试操作数据（由 scripts/prelaunch_data_cleanup.py --print-sql 生成，不要手工改）。
-- 只删除操作数据；账号、班级、学校设置、AI 设置、题库、试卷、审计和反馈记录都保留。
--
--   【已停用】系统正式使用后这是真实数据，必须加 -v allow_after_launch=1 才会运行。
--   演习（什么都不会改，最后自动回滚）：  psql "$DATABASE_URL" -v allow_after_launch=1 -f scripts/prelaunch_data_cleanup.sql
--   正式删除（先备份！）：               psql "$DATABASE_URL" -v allow_after_launch=1 -v do_commit=1 -f scripts/prelaunch_data_cleanup.sql

\set ON_ERROR_STOP on
\if :{?allow_after_launch}
\else
  \echo '系统已正式使用，这个清理脚本已停用：现在库里是真实数据（学习证据、积分、作业提交、AI 辅助记录）。'
  \echo '确实要运行，请加 -v allow_after_launch=1'
  \quit
\endif
\if :{?do_commit}
\else
  \set do_commit 0
\endif

BEGIN;

CREATE TEMP TABLE _keep_before AS
  SELECT 'users' AS tbl, COUNT(*) AS n FROM users
  UNION ALL SELECT 'user_security' AS tbl, COUNT(*) AS n FROM user_security
  UNION ALL SELECT 'schools' AS tbl, COUNT(*) AS n FROM schools
  UNION ALL SELECT 'classes' AS tbl, COUNT(*) AS n FROM classes
  UNION ALL SELECT 'class_students' AS tbl, COUNT(*) AS n FROM class_students
  UNION ALL SELECT 'parent_students' AS tbl, COUNT(*) AS n FROM parent_students
  UNION ALL SELECT 'school_ai_configs' AS tbl, COUNT(*) AS n FROM school_ai_configs
  UNION ALL SELECT 'school_subscriptions' AS tbl, COUNT(*) AS n FROM school_subscriptions
  UNION ALL SELECT 'questions' AS tbl, COUNT(*) AS n FROM questions
  UNION ALL SELECT 'papers' AS tbl, COUNT(*) AS n FROM papers
  UNION ALL SELECT 'audit_logs' AS tbl, COUNT(*) AS n FROM audit_logs;

CREATE TEMP TABLE _deleted (tbl text, n bigint);
WITH d AS (DELETE FROM assignment_question_attempts RETURNING 1) INSERT INTO _deleted SELECT 'assignment_question_attempts', COUNT(*) FROM d;
WITH d AS (DELETE FROM wrong_question_records RETURNING 1) INSERT INTO _deleted SELECT 'wrong_question_records', COUNT(*) FROM d;
WITH d AS (DELETE FROM teaching_attempts RETURNING 1) INSERT INTO _deleted SELECT 'teaching_attempts', COUNT(*) FROM d;
WITH d AS (DELETE FROM submissions RETURNING 1) INSERT INTO _deleted SELECT 'submissions', COUNT(*) FROM d;
WITH d AS (DELETE FROM student_followup_logs RETURNING 1) INSERT INTO _deleted SELECT 'student_followup_logs', COUNT(*) FROM d;
WITH d AS (DELETE FROM reinforcement_links RETURNING 1) INSERT INTO _deleted SELECT 'reinforcement_links', COUNT(*) FROM d;
WITH d AS (DELETE FROM homework_media_submits RETURNING 1) INSERT INTO _deleted SELECT 'homework_media_submits', COUNT(*) FROM d;
WITH d AS (DELETE FROM homework_media RETURNING 1) INSERT INTO _deleted SELECT 'homework_media', COUNT(*) FROM d;
WITH d AS (DELETE FROM assignment_submission_settings RETURNING 1) INSERT INTO _deleted SELECT 'assignment_submission_settings', COUNT(*) FROM d;
WITH d AS (DELETE FROM assignment_retry_grants RETURNING 1) INSERT INTO _deleted SELECT 'assignment_retry_grants', COUNT(*) FROM d;
WITH d AS (DELETE FROM assignment_recipients RETURNING 1) INSERT INTO _deleted SELECT 'assignment_recipients', COUNT(*) FROM d;
WITH d AS (DELETE FROM assignment_drafts RETURNING 1) INSERT INTO _deleted SELECT 'assignment_drafts', COUNT(*) FROM d;
WITH d AS (DELETE FROM ai_grading_reviews RETURNING 1) INSERT INTO _deleted SELECT 'ai_grading_reviews', COUNT(*) FROM d;
WITH d AS (DELETE FROM teaching_essays RETURNING 1) INSERT INTO _deleted SELECT 'teaching_essays', COUNT(*) FROM d;
WITH d AS (DELETE FROM teaching_adaptive_sessions RETURNING 1) INSERT INTO _deleted SELECT 'teaching_adaptive_sessions', COUNT(*) FROM d;
WITH d AS (DELETE FROM student_followups RETURNING 1) INSERT INTO _deleted SELECT 'student_followups', COUNT(*) FROM d;
WITH d AS (DELETE FROM point_ledger RETURNING 1) INSERT INTO _deleted SELECT 'point_ledger', COUNT(*) FROM d;
WITH d AS (DELETE FROM homework_recipients RETURNING 1) INSERT INTO _deleted SELECT 'homework_recipients', COUNT(*) FROM d;
WITH d AS (DELETE FROM help_requests RETURNING 1) INSERT INTO _deleted SELECT 'help_requests', COUNT(*) FROM d;
WITH d AS (DELETE FROM class_todos RETURNING 1) INSERT INTO _deleted SELECT 'class_todos', COUNT(*) FROM d;
WITH d AS (DELETE FROM auto_reward_grants RETURNING 1) INSERT INTO _deleted SELECT 'auto_reward_grants', COUNT(*) FROM d;
WITH d AS (DELETE FROM assignments RETURNING 1) INSERT INTO _deleted SELECT 'assignments', COUNT(*) FROM d;
WITH d AS (DELETE FROM reward_redemptions RETURNING 1) INSERT INTO _deleted SELECT 'reward_redemptions', COUNT(*) FROM d;
WITH d AS (DELETE FROM learning_evidence_events RETURNING 1) INSERT INTO _deleted SELECT 'learning_evidence_events', COUNT(*) FROM d;
WITH d AS (DELETE FROM homework_notices RETURNING 1) INSERT INTO _deleted SELECT 'homework_notices', COUNT(*) FROM d;
WITH d AS (DELETE FROM ai_usage_logs RETURNING 1) INSERT INTO _deleted SELECT 'ai_usage_logs', COUNT(*) FROM d;
WITH d AS (DELETE FROM account_deletion_requests RETURNING 1) INSERT INTO _deleted SELECT 'account_deletion_requests', COUNT(*) FROM d;
WITH d AS (DELETE FROM weekend_written_submissions RETURNING 1) INSERT INTO _deleted SELECT 'weekend_written_submissions', COUNT(*) FROM d;
WITH d AS (DELETE FROM weekend_written_submission_versions RETURNING 1) INSERT INTO _deleted SELECT 'weekend_written_submission_versions', COUNT(*) FROM d;
WITH d AS (DELETE FROM weekend_written_prechecks RETURNING 1) INSERT INTO _deleted SELECT 'weekend_written_prechecks', COUNT(*) FROM d;
WITH d AS (DELETE FROM weekend_written_hint_log RETURNING 1) INSERT INTO _deleted SELECT 'weekend_written_hint_log', COUNT(*) FROM d;
WITH d AS (DELETE FROM weekend_written_annotations RETURNING 1) INSERT INTO _deleted SELECT 'weekend_written_annotations', COUNT(*) FROM d;
WITH d AS (DELETE FROM weekend_stage_log RETURNING 1) INSERT INTO _deleted SELECT 'weekend_stage_log', COUNT(*) FROM d;
WITH d AS (DELETE FROM weekend_stage6_checks RETURNING 1) INSERT INTO _deleted SELECT 'weekend_stage6_checks', COUNT(*) FROM d;
WITH d AS (DELETE FROM weekend_slide_state RETURNING 1) INSERT INTO _deleted SELECT 'weekend_slide_state', COUNT(*) FROM d;
WITH d AS (DELETE FROM weekend_sessions RETURNING 1) INSERT INTO _deleted SELECT 'weekend_sessions', COUNT(*) FROM d;
WITH d AS (DELETE FROM weekend_session_workflows RETURNING 1) INSERT INTO _deleted SELECT 'weekend_session_workflows', COUNT(*) FROM d;
WITH d AS (DELETE FROM weekend_session_questions RETURNING 1) INSERT INTO _deleted SELECT 'weekend_session_questions', COUNT(*) FROM d;
WITH d AS (DELETE FROM weekend_schedule RETURNING 1) INSERT INTO _deleted SELECT 'weekend_schedule', COUNT(*) FROM d;
WITH d AS (DELETE FROM weekend_reports RETURNING 1) INSERT INTO _deleted SELECT 'weekend_reports', COUNT(*) FROM d;
WITH d AS (DELETE FROM weekend_peer_help RETURNING 1) INSERT INTO _deleted SELECT 'weekend_peer_help', COUNT(*) FROM d;
WITH d AS (DELETE FROM weekend_open_questions RETURNING 1) INSERT INTO _deleted SELECT 'weekend_open_questions', COUNT(*) FROM d;
WITH d AS (DELETE FROM weekend_metrics RETURNING 1) INSERT INTO _deleted SELECT 'weekend_metrics', COUNT(*) FROM d;
WITH d AS (DELETE FROM weekend_lesson_materials RETURNING 1) INSERT INTO _deleted SELECT 'weekend_lesson_materials', COUNT(*) FROM d;
WITH d AS (DELETE FROM weekend_hint_log RETURNING 1) INSERT INTO _deleted SELECT 'weekend_hint_log', COUNT(*) FROM d;
WITH d AS (DELETE FROM weekend_class_rosters RETURNING 1) INSERT INTO _deleted SELECT 'weekend_class_rosters', COUNT(*) FROM d;
WITH d AS (DELETE FROM weekend_briefs RETURNING 1) INSERT INTO _deleted SELECT 'weekend_briefs', COUNT(*) FROM d;
WITH d AS (DELETE FROM weekend_awards RETURNING 1) INSERT INTO _deleted SELECT 'weekend_awards', COUNT(*) FROM d;
WITH d AS (DELETE FROM weekend_answers RETURNING 1) INSERT INTO _deleted SELECT 'weekend_answers', COUNT(*) FROM d;
WITH d AS (DELETE FROM student_transition_plans RETURNING 1) INSERT INTO _deleted SELECT 'student_transition_plans', COUNT(*) FROM d;
WITH d AS (DELETE FROM node_reveal_states RETURNING 1) INSERT INTO _deleted SELECT 'node_reveal_states', COUNT(*) FROM d;
WITH d AS (DELETE FROM math_sprint_attempts RETURNING 1) INSERT INTO _deleted SELECT 'math_sprint_attempts', COUNT(*) FROM d;
WITH d AS (DELETE FROM math_node_quizzes RETURNING 1) INSERT INTO _deleted SELECT 'math_node_quizzes', COUNT(*) FROM d;
WITH d AS (DELETE FROM math_node_mastery RETURNING 1) INSERT INTO _deleted SELECT 'math_node_mastery', COUNT(*) FROM d;
WITH d AS (DELETE FROM english_sprint_attempts RETURNING 1) INSERT INTO _deleted SELECT 'english_sprint_attempts', COUNT(*) FROM d;
WITH d AS (DELETE FROM english_node_quizzes RETURNING 1) INSERT INTO _deleted SELECT 'english_node_quizzes', COUNT(*) FROM d;
WITH d AS (DELETE FROM english_node_mastery RETURNING 1) INSERT INTO _deleted SELECT 'english_node_mastery', COUNT(*) FROM d;
WITH d AS (DELETE FROM knowledge_map_runs RETURNING 1) INSERT INTO _deleted SELECT 'knowledge_map_runs', COUNT(*) FROM d;
WITH d AS (DELETE FROM knowledge_map_ratings RETURNING 1) INSERT INTO _deleted SELECT 'knowledge_map_ratings', COUNT(*) FROM d;
WITH d AS (DELETE FROM exam_reports RETURNING 1) INSERT INTO _deleted SELECT 'exam_reports', COUNT(*) FROM d;
WITH d AS (DELETE FROM exam_goals RETURNING 1) INSERT INTO _deleted SELECT 'exam_goals', COUNT(*) FROM d;
WITH d AS (DELETE FROM exam_goal_papers RETURNING 1) INSERT INTO _deleted SELECT 'exam_goal_papers', COUNT(*) FROM d;
WITH d AS (DELETE FROM exam_goal_drills RETURNING 1) INSERT INTO _deleted SELECT 'exam_goal_drills', COUNT(*) FROM d;
WITH d AS (DELETE FROM exam_attempts RETURNING 1) INSERT INTO _deleted SELECT 'exam_attempts', COUNT(*) FROM d;
WITH d AS (DELETE FROM classroom_sessions RETURNING 1) INSERT INTO _deleted SELECT 'classroom_sessions', COUNT(*) FROM d;
WITH d AS (DELETE FROM classroom_segments RETURNING 1) INSERT INTO _deleted SELECT 'classroom_segments', COUNT(*) FROM d;
WITH d AS (DELETE FROM classroom_review_handouts RETURNING 1) INSERT INTO _deleted SELECT 'classroom_review_handouts', COUNT(*) FROM d;
WITH d AS (DELETE FROM classroom_quick_checks RETURNING 1) INSERT INTO _deleted SELECT 'classroom_quick_checks', COUNT(*) FROM d;
WITH d AS (DELETE FROM classroom_quick_check_responses RETURNING 1) INSERT INTO _deleted SELECT 'classroom_quick_check_responses', COUNT(*) FROM d;
WITH d AS (DELETE FROM classroom_presenter_turns RETURNING 1) INSERT INTO _deleted SELECT 'classroom_presenter_turns', COUNT(*) FROM d;
WITH d AS (DELETE FROM classroom_presentation_reviews RETURNING 1) INSERT INTO _deleted SELECT 'classroom_presentation_reviews', COUNT(*) FROM d;
WITH d AS (DELETE FROM classroom_handout_releases RETURNING 1) INSERT INTO _deleted SELECT 'classroom_handout_releases', COUNT(*) FROM d;
WITH d AS (DELETE FROM classroom_events RETURNING 1) INSERT INTO _deleted SELECT 'classroom_events', COUNT(*) FROM d;

UPDATE user_security SET failed_login_count = 0, locked_until = NULL;

\echo '=== 每张表删除的行数 ==='
SELECT tbl AS "表", n AS "删除行数" FROM _deleted WHERE n > 0 ORDER BY tbl;
SELECT COALESCE(SUM(n), 0) AS "合计" FROM _deleted;

CREATE TEMP TABLE _keep_after AS
  SELECT 'users' AS tbl, COUNT(*) AS n FROM users
  UNION ALL SELECT 'user_security' AS tbl, COUNT(*) AS n FROM user_security
  UNION ALL SELECT 'schools' AS tbl, COUNT(*) AS n FROM schools
  UNION ALL SELECT 'classes' AS tbl, COUNT(*) AS n FROM classes
  UNION ALL SELECT 'class_students' AS tbl, COUNT(*) AS n FROM class_students
  UNION ALL SELECT 'parent_students' AS tbl, COUNT(*) AS n FROM parent_students
  UNION ALL SELECT 'school_ai_configs' AS tbl, COUNT(*) AS n FROM school_ai_configs
  UNION ALL SELECT 'school_subscriptions' AS tbl, COUNT(*) AS n FROM school_subscriptions
  UNION ALL SELECT 'questions' AS tbl, COUNT(*) AS n FROM questions
  UNION ALL SELECT 'papers' AS tbl, COUNT(*) AS n FROM papers
  UNION ALL SELECT 'audit_logs' AS tbl, COUNT(*) AS n FROM audit_logs;

\echo '=== 保留的表（前后数量必须一致，下面不能有任何行）==='
SELECT b.tbl AS "表", b.n AS "删除前", a.n AS "删除后" FROM _keep_before b JOIN _keep_after a USING (tbl) WHERE b.n <> a.n;

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM _keep_before b JOIN _keep_after a USING (tbl) WHERE b.n <> a.n) THEN
    RAISE EXCEPTION '保留的表数量发生了变化，已中止并回滚';
  END IF;
END $$;

\if :do_commit
  COMMIT;
  \echo '已提交：测试操作数据已删除。'
\else
  ROLLBACK;
  \echo '演习：没有改动任何数据（已回滚）。要正式删除请加 -v do_commit=1。'
\endif
