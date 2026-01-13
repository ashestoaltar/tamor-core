// ui/src/utils/formatUtc.js

export function formatUtcTimestamp(ts) {
  if (!ts) return "";

  let s = String(ts).trim();

  // If it already has timezone info, trust it
  if (/[zZ]$/.test(s) || /[+\-]\d{2}:\d{2}$/.test(s)) {
    const d = new Date(s);
    return isNaN(d.getTime()) ? s : d.toLocaleString();
  }

  // SQLite style: "YYYY-MM-DD HH:MM:SS(.ffffff)"
  if (/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}/.test(s)) {
    s = s.replace(" ", "T") + "Z";
  }
  // ISO-ish but NO timezone: "YYYY-MM-DDTHH:MM:SS(.fff)"
  else if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}/.test(s)) {
    s = s + "Z";
  }

  const d = new Date(s);
  return isNaN(d.getTime()) ? ts : d.toLocaleString();
}

