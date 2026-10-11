-- Rollback for the after-school homework assistant migration (PR1).
-- Drops ONLY the three tables added by that PR, children first. Touches no other table.
-- Rehearse on a scratch database first. Also revert the PR1 merge commit, otherwise the next
-- application start runs create_all and recreates these (empty) tables.
DROP TABLE IF EXISTS help_requests;
DROP TABLE IF EXISTS homework_recipients;
DROP TABLE IF EXISTS homework_notices;
