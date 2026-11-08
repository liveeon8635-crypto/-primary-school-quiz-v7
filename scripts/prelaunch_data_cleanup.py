#!/usr/bin/env python3
"""Pre-launch cleanup: delete the test *activity* data, keep every account and all configuration.

Safe by default: without ``--execute`` it only prints what it WOULD delete and then rolls back.

    DISABLED since the system went live (the data is real). Every run needs --allow-after-launch:
    DATABASE_URL=... python scripts/prelaunch_data_cleanup.py --allow-after-launch              # dry run
    DATABASE_URL=... python scripts/prelaunch_data_cleanup.py --allow-after-launch --execute --i-have-a-backup

Rules the script enforces itself:
  * every table in the database must be classified below as KEEP or DELETE; an unknown table aborts the run
    (so a table added later is never deleted - or forgotten - by accident);
  * accounts, classes, class membership, schools, AI settings (including the encrypted key), subscriptions,
    rules, questions, papers, teaching content, audit logs and product-feedback records are KEEP;
  * the whole run is ONE transaction; afterwards the row counts of all KEEP tables are compared with the
    counts before, and any difference rolls everything back;
  * it prints table names and row counts only - never row contents, never the database URL.
"""

from __future__ import annotations

import argparse
import os
import sys

from sqlalchemy import MetaData, create_engine, text

# Operation data created by using the accounts. Safe to remove; nothing here is needed to log in or to teach.
DELETE_TABLES = (
    "weekend_written_prechecks",  # provisional suggestions, never formal marks
    # homework and answers
    "submissions", "assignment_recipients", "assignment_submission_settings", "ai_grading_reviews",
    "reinforcement_links", "assignments", "homework_media", "homework_media_submits", "wrong_question_records",
    # points, rewards, learning evidence
    "point_ledger", "reward_redemptions", "auto_reward_grants", "learning_evidence_events",
    # classroom sessions
    "classroom_events", "weekend_class_rosters", "weekend_sessions", "weekend_stage_log", "weekend_hint_log", "weekend_answers", "weekend_written_submissions", "weekend_written_hint_log", "weekend_peer_help", "weekend_awards", "weekend_metrics", "weekend_briefs", "weekend_reports", "weekend_schedule", "weekend_slide_state", "classroom_sessions", "classroom_segments", "classroom_quick_checks",
    "classroom_quick_check_responses", "classroom_presenter_turns", "classroom_presentation_reviews",
    "classroom_review_handouts", "classroom_handout_releases", "class_todos",
    # 定制教学 practice records
    "teaching_attempts", "teaching_adaptive_sessions", "teaching_essays",
    # follow-ups / transition plans
    "student_followups", "student_followup_logs", "student_transition_plans",
    # 晚托作业助手
    "homework_notices", "homework_recipients", "help_requests",
    # 知识地图诊断（学生作答记录）
    "knowledge_map_runs", "knowledge_map_ratings",
    # 应试专项（考试目标和模拟卷，模拟卷本身是作业）
    "exam_goals", "exam_goal_papers", "exam_goal_drills", "exam_attempts", "exam_reports",
    # usage and housekeeping logs
    "ai_usage_logs", "account_deletion_requests",
)

# Accounts, structure, configuration and content. Never touched.
KEEP_TABLES = (
    "schools", "users", "user_security", "parent_students", "classes", "class_students", "student_class_history",
    "classroom_groups", "classroom_group_members",
    "school_ai_configs", "school_subscriptions", "subscription_events",
    "commercial_customers", "commercial_followups", "commercial_operation_logs", "commercial_orders",
    "commercial_payments", "commercial_quota_overrides", "commercial_renewals",
    "point_rules", "class_point_rules", "reward_items", "auto_reward_rules",
    "homework_ai_knowledge",
    "kp_cards", "weekend_hints", "weekend_written_questions", "weekend_courseware", "weekend_courseware_template", "weekend_plan_import_history",
    "knowledge_maps",
    "kp_card_images",
    "questions", "papers", "import_jobs",
    "teaching_programs", "teaching_lessons", "teaching_questions", "teaching_resources",
    "audit_logs", "product_feedback_attachments", "product_feedback_followup_attachments", "product_feedback_rewards",
    "schema_migrations",
)

CONFIRM_FLAG = "--i-have-a-backup"
LAUNCH_FLAG = "--allow-after-launch"
LAUNCH_NOTICE = (
    "This cleanup was for the days BEFORE the system went live and is now disabled: the data in the database is real "
    "(learning evidence, points, submissions, AI-help records). To run it anyway, add " + LAUNCH_FLAG + "."
)

# Counted before and after, so the SQL version can prove it did not touch accounts or configuration.
SQL_CHECK_TABLES = ("users", "user_security", "schools", "classes", "class_students", "parent_students",
                    "school_ai_configs", "school_subscriptions", "questions", "papers", "audit_logs")


def normalize_url(url: str) -> str:
    """Same rewriting as app_v924.py: the app only ships the psycopg (v3) driver."""
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    if url.startswith("postgresql://") and "+psycopg" not in url:
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


def delete_order(meta: MetaData) -> list[str]:
    """DELETE tables that exist, children first so foreign keys never block a delete."""
    present = {t.name for t in meta.tables.values()}
    return [t.name for t in reversed(meta.sorted_tables) if t.name in set(DELETE_TABLES) and t.name in present]


def render_sql(order: list[str]) -> str:
    """The same cleanup for ``psql`` (no Python needed): dry run by default, ``-v do_commit=1`` to really delete."""
    lines = [
        "-- 正式使用前清理测试操作数据（由 scripts/prelaunch_data_cleanup.py --print-sql 生成，不要手工改）。",
        "-- 只删除操作数据；账号、班级、学校设置、AI 设置、题库、试卷、审计和反馈记录都保留。",
        "--",
        "--   【已停用】系统正式使用后这是真实数据，必须加 -v allow_after_launch=1 才会运行。",
        "--   演习（什么都不会改，最后自动回滚）：  psql \"$DATABASE_URL\" -v allow_after_launch=1 -f scripts/prelaunch_data_cleanup.sql",
        "--   正式删除（先备份！）：               psql \"$DATABASE_URL\" -v allow_after_launch=1 -v do_commit=1 -f scripts/prelaunch_data_cleanup.sql",
        "",
        "\\set ON_ERROR_STOP on",
        "\\if :{?allow_after_launch}",
        "\\else",
        "  \\echo '系统已正式使用，这个清理脚本已停用：现在库里是真实数据（学习证据、积分、作业提交、AI 辅助记录）。'",
        "  \\echo '确实要运行，请加 -v allow_after_launch=1'",
        "  \\quit",
        "\\endif",
        "\\if :{?do_commit}",
        "\\else",
        "  \\set do_commit 0",
        "\\endif",
        "",
        "BEGIN;",
        "",
        "CREATE TEMP TABLE _keep_before AS",
        "  " + "\n  UNION ALL ".join(f"SELECT '{t}' AS tbl, COUNT(*) AS n FROM {t}" for t in SQL_CHECK_TABLES) + ";",
        "",
        "CREATE TEMP TABLE _deleted (tbl text, n bigint);",
    ]
    for name in order:
        lines.append(f"WITH d AS (DELETE FROM {name} RETURNING 1) INSERT INTO _deleted SELECT '{name}', COUNT(*) FROM d;")
    lines += [
        "",
        "UPDATE user_security SET failed_login_count = 0, locked_until = NULL;",
        "",
        "\\echo '=== 每张表删除的行数 ==='",
        "SELECT tbl AS \"表\", n AS \"删除行数\" FROM _deleted WHERE n > 0 ORDER BY tbl;",
        "SELECT COALESCE(SUM(n), 0) AS \"合计\" FROM _deleted;",
        "",
        "CREATE TEMP TABLE _keep_after AS",
        "  " + "\n  UNION ALL ".join(f"SELECT '{t}' AS tbl, COUNT(*) AS n FROM {t}" for t in SQL_CHECK_TABLES) + ";",
        "",
        "\\echo '=== 保留的表（前后数量必须一致，下面不能有任何行）==='",
        "SELECT b.tbl AS \"表\", b.n AS \"删除前\", a.n AS \"删除后\" FROM _keep_before b JOIN _keep_after a USING (tbl) WHERE b.n <> a.n;",
        "",
        "DO $$",
        "BEGIN",
        "  IF EXISTS (SELECT 1 FROM _keep_before b JOIN _keep_after a USING (tbl) WHERE b.n <> a.n) THEN",
        "    RAISE EXCEPTION '保留的表数量发生了变化，已中止并回滚';",
        "  END IF;",
        "END $$;",
        "",
        "\\if :do_commit",
        "  COMMIT;",
        "  \\echo '已提交：测试操作数据已删除。'",
        "\\else",
        "  ROLLBACK;",
        "  \\echo '演习：没有改动任何数据（已回滚）。要正式删除请加 -v do_commit=1。'",
        "\\endif",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--execute", action="store_true", help="really delete (default: dry run, rolled back)")
    parser.add_argument(CONFIRM_FLAG, dest="backup", action="store_true", help="required with --execute")
    parser.add_argument("--print-sql", action="store_true", help="print the psql version of this cleanup and exit")
    parser.add_argument(LAUNCH_FLAG, dest="allow_after_launch", action="store_true", help="the system is live; only use if you really mean it")
    args = parser.parse_args(argv)

    if not args.print_sql and not args.allow_after_launch:
        print(LAUNCH_NOTICE, file=sys.stderr)
        return 5
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        print("DATABASE_URL is not set.", file=sys.stderr)
        return 2
    url = normalize_url(url)
    if args.execute and not args.backup:
        print(f"Refusing to delete without {CONFIRM_FLAG}: take a backup first.", file=sys.stderr)
        return 2

    engine = create_engine(url)
    meta = MetaData()
    meta.reflect(bind=engine)
    if args.print_sql:
        sys.stdout.write(render_sql(delete_order(meta)))
        return 0
    present = set(meta.tables)
    unknown = sorted(present - set(DELETE_TABLES) - set(KEEP_TABLES))
    if unknown:
        print("Unclassified tables - decide KEEP or DELETE for each, then update the script:", file=sys.stderr)
        for name in unknown:
            print(f"  {name}", file=sys.stderr)
        return 3
    overlap = set(DELETE_TABLES) & set(KEEP_TABLES)
    if overlap:
        print(f"Tables listed as both KEEP and DELETE: {sorted(overlap)}", file=sys.stderr)
        return 3

    order = delete_order(meta)
    keep_present = [name for name in KEEP_TABLES if name in present]

    def count(conn, name: str) -> int:
        return int(conn.execute(text(f'SELECT COUNT(*) FROM "{name}"')).scalar() or 0)

    with engine.connect() as conn:
        trans = conn.begin()
        try:
            before_keep = {name: count(conn, name) for name in keep_present}
            to_delete = {name: count(conn, name) for name in order}
            for name in order:
                conn.execute(text(f'DELETE FROM "{name}"'))
            reset_locks = 0
            if "user_security" in present:
                reset_locks = int(conn.execute(text(
                    "SELECT COUNT(*) FROM user_security WHERE failed_login_count <> 0 OR locked_until IS NOT NULL"
                )).scalar() or 0)
                conn.execute(text("UPDATE user_security SET failed_login_count = 0, locked_until = NULL"))
            after_keep = {name: count(conn, name) for name in keep_present}
            changed = {n: (before_keep[n], after_keep[n]) for n in keep_present if before_keep[n] != after_keep[n]}
            left = {name: count(conn, name) for name in order if count(conn, name)}
            if changed or left:
                trans.rollback()
                print("ABORTED and rolled back. Kept tables changed or delete tables not empty:", changed, left, file=sys.stderr)
                return 4
            summary_delete = sum(to_delete.values())
            print(f"{'EXECUTE' if args.execute else 'DRY RUN'} - rows deleted per table:")
            for name in order:
                print(f"  {name:38s} {to_delete[name]:>8d}")
            print(f"  {'TOTAL':38s} {summary_delete:>8d}")
            print(f"login-failure counters reset on {reset_locks} account(s)")
            print("kept (unchanged):")
            for name in keep_present:
                print(f"  {name:38s} {after_keep[name]:>8d}")
            if args.execute:
                trans.commit()
                print("COMMITTED.")
            else:
                trans.rollback()
                print("Dry run: nothing was changed.")
        except Exception:
            trans.rollback()
            raise
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

