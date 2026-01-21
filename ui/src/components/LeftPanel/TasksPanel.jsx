import React, { useEffect, useMemo, useState } from "react";
import { apiFetch } from "../../api/client";
import { formatUtcTimestamp } from "../../utils/formatUtc";

const CHIP = {
  padding: "6px 10px",
  borderRadius: 999,
  border: "1px solid rgba(255,255,255,0.14)",
  background: "rgba(255,255,255,0.04)",
  cursor: "pointer",
  fontSize: 12,
  opacity: 0.95,
  userSelect: "none",
};



export default function TasksPanel({ onOpenConversation }) {
  const [status, setStatus] = useState("needs_confirmation");
  const [taskType, setTaskType] = useState("");
  const [limit, setLimit] = useState(100);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [tasks, setTasks] = useState([]);

  const queryString = useMemo(() => {
    const qs = new URLSearchParams();
    if (status) qs.set("status", status);
    if (taskType.trim()) qs.set("task_type", taskType.trim());
    qs.set("limit", String(limit));
    return qs.toString();
  }, [status, taskType, limit]);

  const load = async () => {
    setBusy(true);
    setErr("");
    try {
      const res = await apiFetch(`/tasks?${queryString}`);
      setTasks(res.tasks || []);
    } catch (e) {
      setErr(e?.message || "Failed to load tasks.");
      setTasks([]);
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [queryString]);

  // TaskPill (chat) emits this. TasksPanel refreshes.
  useEffect(() => {
    const handler = () => load();
    window.addEventListener("tamor:tasks-updated", handler);
    return () => window.removeEventListener("tamor:tasks-updated", handler);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [queryString]);

  const setTaskStatus = async (taskId, next) => {
    setBusy(true);
    setErr("");

    try {
      if (next === "dismissed" || next === "confirmed") {
        await apiFetch(`/tasks/${taskId}/status`, { method: "POST", body: { status: next } });
      } else {
        const endpoint =
          next === "confirmed"
            ? `/tasks/${taskId}/confirm`
            : next === "cancelled"
            ? `/tasks/${taskId}/cancel`
            : next === "completed"
            ? `/tasks/${taskId}/complete`
            : null;

        if (!endpoint) throw new Error(`Unsupported transition: ${next}`);
        await apiFetch(endpoint, { method: "POST" });
      }

      // ✅ single refresh. No event dispatch here (prevents double-refresh).
      await load();
    } catch (e) {
      setErr(e?.message || "Failed to update task status.");
    } finally {
      setBusy(false);
    }
  };

  const deleteTask = async (taskId) => {
    if (!window.confirm("Delete this task permanently?")) return;

    setBusy(true);
    setErr("");

    try {
      await apiFetch(`/tasks/${taskId}`, { method: "DELETE" });
      await load();
    } catch (e) {
      setErr(e?.message || "Failed to delete task.");
    } finally {
      setBusy(false);
    }
  };

  const chips = [
    { label: "Needs confirmation", value: "needs_confirmation" },
    { label: "Scheduled", value: "confirmed" },
    { label: "Paused", value: "dismissed" },
    { label: "Done", value: "completed" },
    { label: "Cancelled", value: "cancelled" },
  ];

  return (
    <div style={{ padding: 12 }}>
      <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", gap: 10 }}>
        <div style={{ fontSize: 18, fontWeight: 800 }}>Tasks</div>
        <button type="button" onClick={load} disabled={busy}>
          Refresh
        </button>
      </div>

      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 10 }}>
        {chips.map((c) => (
          <div
            key={c.value}
            style={{
              ...CHIP,
              background: status === c.value ? "rgba(255,255,255,0.10)" : CHIP.background,
              border: status === c.value ? "1px solid rgba(255,255,255,0.22)" : CHIP.border,
            }}
            onClick={() => setStatus(c.value)}
          >
            {c.label}
          </div>
        ))}

        <div style={{ ...CHIP, opacity: 0.75 }} onClick={() => setStatus("")}>
          All
        </div>
      </div>

      <div style={{ marginTop: 12, display: "grid", gap: 10 }}>
        <div>
          <div style={{ fontSize: 12, opacity: 0.7, marginBottom: 6 }}>Task type (optional)</div>
          <input
            value={taskType}
            onChange={(e) => setTaskType(e.target.value)}
            placeholder={`e.g. "reminder"`}
            style={{ width: "100%" }}
          />
        </div>

        <div>
          <div style={{ fontSize: 12, opacity: 0.7, marginBottom: 6 }}>Limit</div>
          <input
            type="number"
            min={1}
            max={200}
            value={limit}
            onChange={(e) => setLimit(parseInt(e.target.value || "100", 10))}
            style={{ width: "100%" }}
          />
        </div>

        {err ? <div style={{ color: "salmon" }}>API error: {err}</div> : null}
      </div>

      <div style={{ display: "grid", gap: 10, marginTop: 12 }}>
        {tasks.map((t) => {
          const scheduledFor = t.normalized?.scheduled_for || null;
          const isRecurring = Boolean(t.normalized?.recurrence || t.normalized?.rrule);

          return (
            <div
              key={t.id}
              style={{
                border: "1px solid rgba(255,255,255,0.12)",
                borderRadius: 14,
                padding: 12,
                background: "rgba(255,255,255,0.03)",
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", gap: 10 }}>
                <div style={{ fontWeight: 800 }}>
                  {(t.task_type || "task").toUpperCase()}
                  <span style={{ opacity: 0.7, fontWeight: 500 }}> • {t.status}</span>
                  {isRecurring ? <span style={{ opacity: 0.75 }}> • 🔁</span> : null}
                </div>
                <div style={{ opacity: 0.6, fontSize: 12 }}>
                  {typeof t.confidence === "number" ? `conf ${t.confidence.toFixed(2)}` : ""}
                </div>
              </div>

              <div style={{ marginTop: 6, opacity: 0.95 }}>{t.title}</div>

              {scheduledFor && (
                <div style={{ marginTop: 6, fontSize: 12, opacity: 0.75 }}>
                  Next run: {formatUtcTimestamp(scheduledFor, undefined, {
                    weekday: "short",
                    month: "short",
                    day: "2-digit",
                    hour: "numeric",
                    minute: "2-digit",
                  })}
                </div>
              )}

              <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 10 }}>
                {t.status === "needs_confirmation" && (
                  <>
                    <button disabled={busy} onClick={() => setTaskStatus(t.id, "confirmed")}>
                      Confirm
                    </button>
                    <button disabled={busy} onClick={() => setTaskStatus(t.id, "cancelled")}>
                      Cancel
                    </button>
                  </>
                )}

                {t.status === "confirmed" && (
                  <>
                    {isRecurring ? (
                      <button disabled={busy} onClick={() => setTaskStatus(t.id, "dismissed")}>
                        Pause
                      </button>
                    ) : (
                      <button disabled={busy} onClick={() => setTaskStatus(t.id, "completed")}>
                        Complete
                      </button>
                    )}
                    <button disabled={busy} onClick={() => setTaskStatus(t.id, "cancelled")}>
                      Cancel
                    </button>
                  </>
                )}

                {t.status === "dismissed" && (
                  <>
                    <button disabled={busy} onClick={() => setTaskStatus(t.id, "confirmed")}>
                      Resume
                    </button>
                    <button disabled={busy} onClick={() => setTaskStatus(t.id, "cancelled")}>
                      Cancel
                    </button>
                  </>
                )}

                {/* Delete available for all non-running tasks */}
                <button
                  disabled={busy}
                  onClick={() => deleteTask(t.id)}
                  style={{ opacity: 0.7 }}
                  title="Delete permanently"
                >
                  Delete
                </button>
              </div>

              {t.conversation_id ? (
                <div style={{ fontSize: 11, opacity: 0.6, marginTop: 8 }}>
                  convo #{t.conversation_id} {t.message_id ? `• msg #${t.message_id}` : ""}{" "}
                  <span
                    style={{ textDecoration: "underline", cursor: "pointer", opacity: 0.8 }}
                    onClick={() => onOpenConversation?.(t.conversation_id)}
                    title="Open conversation"
                  >
                    open
                  </span>
                </div>
              ) : null}
            </div>
          );
        })}
      </div>
    </div>
  );
}

