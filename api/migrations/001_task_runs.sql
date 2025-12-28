BEGIN TRANSACTION;

CREATE TABLE IF NOT EXISTS task_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL,
    started_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at DATETIME,
    status TEXT NOT NULL,
    error_text TEXT,

    FOREIGN KEY (task_id) REFERENCES detected_tasks(id)
);

CREATE INDEX IF NOT EXISTS idx_task_runs_task
    ON task_runs(task_id);

CREATE INDEX IF NOT EXISTS idx_task_runs_status
    ON task_runs(status);

UPDATE schema_version SET version = 1;

COMMIT;
