import { useState } from "react";

const CATEGORY_LABELS = {
  identity: "Identity",
  preference: "Preference",
  theology: "Theology",
  engineering: "Engineering",
  music: "Music",
  website: "Website",
  tamor_project: "Tamor Project",
  long_note: "Long Note",
  knowledge: "Knowledge",
  knowledge_code: "Code Knowledge",
  knowledge_theology: "Theology Knowledge",
  knowledge_engineering: "Engineering Knowledge",
  conversation: "Conversation",
  project: "Project",
};

const CATEGORY_CLASSES = {
  identity: "tag tag-blue",
  preference: "tag tag-cyan",
  theology: "tag tag-gold",
  engineering: "tag tag-orange",
  music: "tag tag-purple",
  website: "tag tag-teal",
  tamor_project: "tag tag-amber",
  long_note: "tag tag-gray",
  knowledge: "tag tag-green",
  knowledge_code: "tag tag-green",
  knowledge_theology: "tag tag-green",
  knowledge_engineering: "tag tag-green",
  conversation: "tag tag-neutral",
  project: "tag tag-amber",
};

export default function MemoryCard({ memory, onDelete }) {
  const [expanded, setExpanded] = useState(false);

  const categoryLabel =
    CATEGORY_LABELS[memory.category] || memory.category || "Memory";
  const categoryClass =
    CATEGORY_CLASSES[memory.category] || "tag tag-neutral";

  return (
    <div
      className={`memory-card ${expanded ? "expanded" : ""}`}
      onClick={() => setExpanded((e) => !e)}
    >
      <div className="memory-card-header">
        <span className={categoryClass}>{categoryLabel}</span>
        <button
          className="memory-delete-btn"
          onClick={(e) => {
            e.stopPropagation(); // don't toggle expand
            onDelete(memory.id);
          }}
          title="Delete this memory"
        >
          🗑
        </button>
      </div>

      <div className="memory-card-content">
        <p className="memory-text">{memory.content}</p>
      </div>

      <div className="memory-card-footer">
        <span className="memory-id">#{memory.id}</span>
        <span className="memory-expand-hint">
          {expanded ? "Click to collapse" : "Click to expand"}
        </span>
      </div>
    </div>
  );
}
