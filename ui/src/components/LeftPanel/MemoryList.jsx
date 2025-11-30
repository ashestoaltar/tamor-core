import { useEffect, useState } from "react";
import axios from "axios";
import MemoryCard from "./MemoryCard";
import "../../styles/memory.css";

const CATEGORY_FILTERS = [
  { value: "all", label: "All" },
  { value: "identity", label: "Identity" },
  { value: "preference", label: "Preference" },
  { value: "theology", label: "Theology" },
  { value: "engineering", label: "Engineering" },
  { value: "music", label: "Music" },
  { value: "website", label: "Website" },
  { value: "tamor_project", label: "Tamor Project" },
  { value: "project", label: "Project" },
  { value: "knowledge", label: "Knowledge" },
  { value: "long_note", label: "Long Notes" },
  { value: "conversation", label: "Conversation" },
];

export default function MemoryList() {
  const [memories, setMemories] = useState([]);
  const [loading, setLoading] = useState(false);
  const [category, setCategory] = useState("all");
  const [search, setSearch] = useState("");

  const fetchMemories = async () => {
    try {
      setLoading(true);
      const params = {};
      if (category && category !== "all") params.category = category;
      if (search.trim().length > 0) params.q = search.trim();

      const res = await axios.get("/api/memory/list", { params });
      setMemories(res.data || []);
    } catch (err) {
      console.error("Error fetching memories", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchMemories();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [category]);

  const handleSearchSubmit = (e) => {
    e.preventDefault();
    fetchMemories();
  };

  const handleDelete = async (id) => {
    try {
      await axios.delete(`/api/memory/${id}`);
      setMemories((prev) => prev.filter((m) => m.id !== id));
    } catch (err) {
      console.error("Error deleting memory", err);
    }
  };

  return (
    <div className="memory-panel">
      <h3 className="panel-title">Memory</h3>

      <form className="memory-search" onSubmit={handleSearchSubmit}>
        <input
          type="text"
          placeholder="Search memories..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <button type="submit">Search</button>
      </form>

      <div className="memory-filters">
        {CATEGORY_FILTERS.map((cat) => (
          <button
            key={cat.value}
            type="button"
            className={
              "memory-filter-btn" +
              (category === cat.value ? " active" : "")
            }
            onClick={() => setCategory(cat.value)}
          >
            {cat.label}
          </button>
        ))}
      </div>

      <div className="memory-list">
        {loading && <div className="memory-loading">Loading...</div>}

        {!loading && memories.length === 0 && (
          <div className="memory-empty">
            No memories found. Talk to Tamor or store important things and
            they will appear here.
          </div>
        )}

        {!loading &&
          memories.map((m) => (
            <MemoryCard key={m.id} memory={m} onDelete={handleDelete} />
          ))}
      </div>
    </div>
  );
}

