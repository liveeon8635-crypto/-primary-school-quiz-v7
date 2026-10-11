-- Read-only row counts of core existing tables. Run against production and against the scratch
-- database restored from the backup; the numbers must match (small differences = rows created
-- after the backup was taken, which you should be able to explain).
SELECT 'schools' AS tbl, count(*) AS n FROM schools
UNION ALL SELECT 'users', count(*) FROM users
UNION ALL SELECT 'classes', count(*) FROM classes
UNION ALL SELECT 'class_students', count(*) FROM class_students
UNION ALL SELECT 'questions', count(*) FROM questions
UNION ALL SELECT 'papers', count(*) FROM papers
UNION ALL SELECT 'assignments', count(*) FROM assignments
UNION ALL SELECT 'assignment_recipients', count(*) FROM assignment_recipients
UNION ALL SELECT 'submissions', count(*) FROM submissions
UNION ALL SELECT 'wrong_question_records', count(*) FROM wrong_question_records
UNION ALL SELECT 'homework_media', count(*) FROM homework_media
UNION ALL SELECT 'school_ai_configs', count(*) FROM school_ai_configs
UNION ALL SELECT 'ai_usage_logs', count(*) FROM ai_usage_logs
ORDER BY 1;
