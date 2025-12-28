import { useEffect, useMemo, useState } from "react";
import { apiFetch } from "../../api/client";

function fmtWhen(iso) {
  if (!iso) return "";
  try {
    const d = new Date(iso);
    return d.toLocaleString(undefined, {
      weekday: "short",
      month: "short",
      day: "2-digit",
      hour: "numeric",
      minute: "2-digit",
    });
  } catch {
    return String(iso);
  }
}

function normalizeStatus(s) {
  if (!s) return s;
  if (s === "canceled") return "cancelled";
  return s;
}

function statusLabel(s) {
  switch (s) {
    case "needs_confirmation":
      return "Needs confirmation";
    case "confirmed":
      return "Scheduled";
    case "dismissed":
      return "Paused";
    case "completed":
      return "Completed";
    case "cancelled":
      return "Cancelled";
    default:
      return s || "";
  }
}

function statusStyle(status) {
  // subtle, readable chips (no hard-coded bright colors)
  const base = {
    display: "inline-flex",
    alignItems: "center",
    gap: 6,
    padding: "2px 10px",
    borderRadius: 999,
    fontSize: 12,
    border: "1px solid rgba(255,255,255,0.14)",
    background: "rgba(255,255,255,0.05)",
    opacity: 0.95,
    whiteSpace: "nowrap",
  };

  if (status === "needs_confirmation") {
    return { ...base, background: "rgba(255, 180, 60, 0.12)", border: "1px solid rgba(255,180,60,0.25)" };
  }
  if (status === "dismissed") {
    return { ...base, background: "rgba(160,160,255,0.10)", border: "1px solid rgba(160,160,255,0.22)" };
  }
  if (status === "confirmed") {
    return { ...base, background: "rgba(60,180,120,0.10)", border: "1px solid rgba(60,180,120,0.22)" };
  }
  if (status === "completed") {
    return { ...base, background: "rgba(255,255,255,0.06)", opacity: 0.85 };
  }
  if (status === "cancelled") {
    return { ...base, background: "rgba(255,90,90,0.10)", border: "1px solid rgba(255,90,90,0.22)" };
  }
  return base;
}

function recurrenceText(task) {
  const n = task?.normalized || {};
  const r = n.recurrence || n.rrule || null;
  if (!r) return "";

  if (typeof r === "object") {
    const freq = (r.freq || "").toLowerCase();
    if (!freq) return "Repeats";
    if (freq === "daily") return "Repeats: daily";
    if (freq === "weekly") {
      const days = Array.isArray(r.byweekday) ? r.byweekday : [];
      const names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
      const dayStr = days.length ? ` (${days.map((d) => names[d] || "").join(", ")})` : "";
      return `Repeats: weekly${dayStr}`;
    }
    return `Repeats: ${freq}`;
  }

  if (typeof r === "string") return `Repeats: ${r}`;
  return "Repeats";
}

export default function TaskPill({ task, onAppendMessage }) {
  const [expanded, setExpanded] = useState(true);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState(normalizeStatus(task?.status));
  const [err, setErr] = useState("");

  const taskType = (task?.task_type || "task").toUpperCase();
  const title = task?.title || "";
  const whenIso = task?.normalized?.scheduled_for || "";
  const whenTxt = fmtWhen(whenIso);
  const isRecurring = Boolean(task?.normalized?.recurrence || task?.normalized?.rrule);
  const repeats = useMemo(() => recurrenceText(task), [task]);

  // sync if parent updates task
  useEffect(() => {
    setStatus(normalizeStatus(task?.status));
  }, [task?.status]);

  // collapse by default after action states (but still clickable)
  useEffect(() => {
    const autoCollapse = ["confirmed", "completed", "cancelled", "dismissed"];
    if (autoCollapse.includes(status)) setExpanded(false);
  }, [status]);

  const act = async (action) => {
    if (!task?.id || busy) return;
    setBusy(true);
    setErr("");
    try {
      let resp;

      if (action === "pause") {
        resp = await apiFetch(`/tasks/${task.id}/status`, { method: "POST", body: { status: "dismissed" } });
      } else if (action === "resume") {
        resp = await apiFetch(`/tasks/${task.id}/status`, { method: "POST", body: { status: "confirmed" } });
      } else {
        const endpoint =
          action === "confirm"
            ? `/tasks/${task.id}/confirm`
            : action === "cancel"
            ? `/tasks/${task.id}/cancel`
            : `/tasks/${task.id}/complete`;

        resp = await apiFetch(endpoint, { method: "POST" });
      }

      const newStatus = normalizeStatus(resp?.task?.status);
      if (newStatus) setStatus(newStatus);

      // optional: append a short assistant note
      if (onAppendMessage) {
        const msg =
          action === "confirm"
            ? "✅ Task confirmed."
            : action === "cancel"
            ? "❌ Task cancelled."
            : action === "complete"
            ? "✅ Marked complete."
            : action === "pause"
            ? "⏸ Task paused."
            : action === "resume"
            ? "▶️ Task resumed."
            : "✅ Updated.";
        onAppendMessage({ role: "assistant", sender: "tamor", content: msg });
      }

      setExpanded(false);
      window.dispatchEvent(new Event("tamor:tasks-updated"));
    } catch (e) {
      console.error("task action failed", e);
      setErr(e?.message || String(e));
    } finally {
      setBusy(false);
    }
  };

  const showConfirm = status === "needs_confirmation";
  const showConfirmedActions = status === "confirmed";
  const showPausedActions = status === "dismissed";

  return (
    <div
      className="task-pill"
      style={{
        marginTop: 10,
        border: "1px solid rgba(255,255,255,0.12)",
        borderRadius: 14,
        background: "rgba(255,255,255,0.03)",
        overflow: "hidden",
      }}
    >
      <div
        className="task-pill-header"
        role="button"
        tabIndex={0}
        onClick={() => setExpanded((v) => !v)}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") setExpanded((v) => !v);
        }}
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 10,
          padding: "10px 12px",
          cursor: "pointer",
          userSelect: "none",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
          <span
            style={{
              fontWeight: 800,
              letterSpacing: 0.4,
              fontSize: 12,
              opacity: 0.9,
            }}
          >
            {taskType}
          </span>

          <span style={statusStyle(status)}>
            {status === "needs_confirmation" ? "⚠" : status === "dismissed" ? "⏸" : status === "confirmed" ? "✅" : status === "cancelled" ? "❌" : "✅"}{" "}
            {statusLabel(status)}
          </span>

          {isRecurring && (
            <span
              style={{
                display: "inline-flex",
                alignItems: "center",
                padding: "2px 10px",
                borderRadius: 999,
                fontSize: 12,
                border: "1px solid rgba(255,255,255,0.14)",
                background: "rgba(255,255,255,0.04)",
                opacity: 0.9,
                whiteSpace: "nowrap",
              }}
            >
              🔁 Recurring
            </span>
          )}
        </div>

        <div style={{ opacity: 0.8, marginLeft: 8 }}>{expanded ? "▾" : "▸"}</div>
      </div>

      {expanded && (
        <div style={{ padding: "10px 12px", borderTop: "1px solid rgba(255,255,255,0.10)" }}>
          {title ? (
            <div style={{ marginBottom: 6 }}>
              <strong>Details:</strong> <span>{title}</span>
            </div>
          ) : null}

          {whenTxt ? (
            <div style={{ marginBottom: 6 }}>
              <strong>Next run:</strong> <span>{whenTxt}</span>
            </div>
          ) : null}

          {repeats ? <div style={{ marginBottom: 10, opacity: 0.9 }}>{repeats}</div> : null}

          {err ? (
            <div style={{ marginBottom: 10, color: "salmon", fontSize: 13 }}>
              {err}
            </div>
          ) : null}

          {showConfirm && (
            <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
              <button disabled={busy} onClick={() => act("confirm")}>
                ✅ Confirm
              </button>
              <button disabled={busy} onClick={() => act("cancel")}>
                ❌ Cancel
              </button>
            </div>
          )}

          {showConfirmedActions && (
            <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
              {isRecurring ? (
                <button disabled={busy} onClick={() => act("pause")}>
                  ⏸ Pause
                </button>
              ) : (
                <button disabled={busy} onClick={() => act("complete")}>
                  ✅ Mark complete
                </button>
              )}
              <button disabled={busy} onClick={() => act("cancel")}>
                ❌ Cancel
              </button>
            </div>
          )}

          {showPausedActions && (
            <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
              <button disabled={busy} onClick={() => act("resume")}>
                ▶️ Resume
              </button>
              <button disabled={busy} onClick={() => act("cancel")}>
                ❌ Cancel
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

