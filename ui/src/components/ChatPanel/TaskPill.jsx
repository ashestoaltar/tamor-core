import { useEffect, useMemo, useState } from "react";
import { apiFetch } from "../../api/client";
import { formatUtcTimestamp } from "../../utils/formatUtc";

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
    return {
      ...base,
      background: "rgba(255, 170, 0, 0.18)",
      border: "1px solid rgba(255,170,0,0.45)",
      fontWeight: 600,
    };
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

  // Edit mode state
  const [isEditing, setIsEditing] = useState(false);
  const [editTitle, setEditTitle] = useState("");
  const [editScheduledFor, setEditScheduledFor] = useState("");

  const taskId = task?.id;
  const taskType = (task?.task_type || "task").toUpperCase();
  const title = task?.title || "";
  const whenIso = task?.normalized?.scheduled_for || "";
  const whenTxt = formatUtcTimestamp(whenIso, undefined, {
    weekday: "short",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
    timeZoneName: "short",
  });

  const isRecurring = Boolean(task?.normalized?.recurrence || task?.normalized?.rrule);
  const repeats = useMemo(() => recurrenceText(task), [task]);

  useEffect(() => {
    setStatus(normalizeStatus(task?.status));
    setErr("");
    setExpanded(true);
  }, [taskId]);

  useEffect(() => {
    if (["confirmed", "completed", "cancelled", "dismissed"].includes(status)) {
      setExpanded(false);
    }
  }, [status]);

  const act = async (action) => {
    if (!taskId || busy) return;
    setBusy(true);
    setErr("");

    try {
      let resp;
      if (action === "pause") {
        resp = await apiFetch(`/tasks/${taskId}/status`, { method: "POST", body: { status: "dismissed" } });
      } else if (action === "resume") {
        resp = await apiFetch(`/tasks/${taskId}/status`, { method: "POST", body: { status: "confirmed" } });
      } else {
        const endpoint =
          action === "confirm"
            ? `/tasks/${taskId}/confirm`
            : action === "cancel"
            ? `/tasks/${taskId}/cancel`
            : `/tasks/${taskId}/complete`;
        resp = await apiFetch(endpoint, { method: "POST" });
      }

      const newStatus = normalizeStatus(resp?.task?.status);
      if (newStatus) setStatus(newStatus);
      window.dispatchEvent(new Event("tamor:tasks-updated"));
    } catch (e) {
      setErr(e?.message || String(e));
    } finally {
      setBusy(false);
    }
  };

  const startEdit = () => {
    setIsEditing(true);
    setEditTitle(title);
    // Convert UTC ISO string to local datetime-local format
    if (whenIso) {
      const d = new Date(whenIso);
      const local = new Date(d.getTime() - d.getTimezoneOffset() * 60000);
      setEditScheduledFor(local.toISOString().slice(0, 16));
    } else {
      setEditScheduledFor("");
    }
  };

  const cancelEdit = () => {
    setIsEditing(false);
    setEditTitle("");
    setEditScheduledFor("");
  };

  const saveEdit = async () => {
    if (!taskId || busy) return;
    setBusy(true);
    setErr("");

    try {
      const body = {};
      if (editTitle.trim()) body.title = editTitle.trim();
      if (editScheduledFor) {
        body.scheduled_for = new Date(editScheduledFor).toISOString();
      }

      await apiFetch(`/tasks/${taskId}`, { method: "PATCH", body });
      cancelEdit();
      window.dispatchEvent(new Event("tamor:tasks-updated"));
    } catch (e) {
      setErr(e?.message || String(e));
    } finally {
      setBusy(false);
    }
  };

  const deleteTask = async () => {
    if (!taskId || busy) return;
    if (!window.confirm("Delete this task permanently?")) return;

    setBusy(true);
    setErr("");

    try {
      await apiFetch(`/tasks/${taskId}`, { method: "DELETE" });
      setStatus("deleted");
      window.dispatchEvent(new Event("tamor:tasks-updated"));
    } catch (e) {
      setErr(e?.message || String(e));
    } finally {
      setBusy(false);
    }
  };

  // Don't render if deleted
  if (status === "deleted") {
    return (
      <div className="task-pill" style={{ opacity: 0.5, fontStyle: "italic" }}>
        Task deleted
      </div>
    );
  }

  return (
    <div className="task-pill">
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
        <span style={statusStyle(status)}>{statusLabel(status)}</span>
        {isRecurring && <span style={{ opacity: 0.7 }}>🔁</span>}
      </div>

      {isEditing ? (
        <>
          <div style={{ marginTop: 6 }}>
            <input
              type="text"
              value={editTitle}
              onChange={(e) => setEditTitle(e.target.value)}
              placeholder="Task title"
              style={{ width: "100%", marginBottom: 6 }}
            />
            <input
              type="datetime-local"
              value={editScheduledFor}
              onChange={(e) => setEditScheduledFor(e.target.value)}
              style={{ width: "100%" }}
            />
          </div>
          <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
            <button disabled={busy} onClick={saveEdit}>Save</button>
            <button disabled={busy} onClick={cancelEdit} style={{ opacity: 0.7 }}>Cancel</button>
          </div>
        </>
      ) : (
        <>
          {whenTxt && <div><strong>Next run:</strong> {whenTxt}</div>}
          {repeats && <div style={{ opacity: 0.8, fontSize: 13 }}>{repeats}</div>}

          <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 8 }}>
            {status === "needs_confirmation" && (
              <>
                <button disabled={busy} onClick={() => act("confirm")}>Confirm</button>
                <button disabled={busy} onClick={() => act("cancel")}>Cancel</button>
              </>
            )}

            {status === "confirmed" && (
              <>
                {isRecurring ? (
                  <button disabled={busy} onClick={() => act("pause")}>Pause</button>
                ) : (
                  <button disabled={busy} onClick={() => act("complete")}>Complete</button>
                )}
                <button disabled={busy} onClick={() => act("cancel")}>Cancel</button>
              </>
            )}

            {status === "dismissed" && (
              <>
                <button disabled={busy} onClick={() => act("resume")}>Resume</button>
                <button disabled={busy} onClick={() => act("cancel")}>Cancel</button>
              </>
            )}

            {/* Edit & Delete for non-terminal states */}
            {!["completed", "cancelled"].includes(status) && (
              <>
                <button disabled={busy} onClick={startEdit} style={{ opacity: 0.7 }}>Edit</button>
                <button disabled={busy} onClick={deleteTask} style={{ opacity: 0.7 }}>Delete</button>
              </>
            )}
          </div>
        </>
      )}

      {err && <div style={{ color: "salmon", marginTop: 6, fontSize: 12 }}>{err}</div>}
    </div>
  );
}

