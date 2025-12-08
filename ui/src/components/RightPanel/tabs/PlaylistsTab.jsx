// src/components/RightPanel/tabs/PlaylistsTab.jsx
import React, { useState } from "react";
import { apiFetch } from "../../../api/client";

function PlaylistsTab() {
  const [playlistSlug, setPlaylistSlug] = useState("christmas");
  const [playlistLoading, setPlaylistLoading] = useState(false);
  const [playlistError, setPlaylistError] = useState("");
  const [playlistItems, setPlaylistItems] = useState([]);

  const loadPlaylist = async (slug) => {
    setPlaylistLoading(true);
    setPlaylistError("");
    setPlaylistItems([]);

    try {
      const data = await apiFetch(`/playlists/${slug}`);
      const items = (data.playlist && data.items) || data.items || [];
      setPlaylistItems(items);
    } catch (err) {
      console.error("Failed to load playlist", err);
      setPlaylistError("Error loading playlist");
    } finally {
      setPlaylistLoading(false);
    }
  };

  const handleRemoveFromPlaylist = async (slug, title) => {
    if (!title) return;

    try {
      await apiFetch(`/playlists/${slug}`, {
        method: "DELETE",
        body: { title },
      });

      const data = await apiFetch(`/playlists/${slug}`);
      const items = (data.playlist && data.items) || data.items || [];
      setPlaylistItems(items);
    } catch (err) {
      console.error("Failed to remove from playlist", err);
      setPlaylistError("Error updating playlist");
    }
  };

  const currentPlaylistLabel =
    playlistSlug === "christmas"
      ? "Christmas Movies"
      : playlistSlug === "favorites"
      ? "Favorites"
      : playlistSlug === "thanksgiving"
      ? "Thanksgiving"
      : playlistSlug === "kids"
      ? "Kids"
      : playlistSlug;

  return (
    <div className="rp-tab-content">
      <div className="rp-section">
        <div className="rp-section-header">
          <h3 className="rp-section-title">Playlists</h3>
        </div>
        <div className="rp-section-body">
          <div className="rp-playlist-controls">
            <select
              className="rp-input"
              value={playlistSlug}
              onChange={(e) => {
                const slug = e.target.value;
                setPlaylistSlug(slug);
                loadPlaylist(slug);
              }}
            >
              <option value="christmas">Christmas</option>
              <option value="favorites">Favorites</option>
              <option value="thanksgiving">Thanksgiving</option>
              <option value="kids">Kids</option>
            </select>
            <button
              className="rp-button"
              type="button"
              onClick={() => loadPlaylist(playlistSlug)}
              disabled={playlistLoading}
            >
              {playlistLoading ? "Loading…" : "Load"}
            </button>
          </div>
          {playlistError && (
            <div className="rp-error">{playlistError}</div>
          )}
          {playlistItems.length > 0 && (
            <div className="rp-section-sublist rp-playlist-list">
              <div className="rp-small-text rp-muted">
                {currentPlaylistLabel}
              </div>
              {playlistItems.map((item, idx) => (
                <div key={idx} className="rp-hit-row rp-playlist-item">
                  <div className="rp-hit-title">
                    {item.title}{" "}
                    {item.year && (
                      <span className="rp-tag rp-tag-muted">
                        {item.year}
                      </span>
                    )}
                  </div>
                  {item.overview && (
                    <div className="rp-hit-snippet">
                      {item.overview}
                    </div>
                  )}
                  <div className="rp-playlist-actions">
                    {item.poster && (
                      <img
                        src={item.poster}
                        alt={item.title}
                        className="rp-playlist-poster"
                      />
                    )}
                    <button
                      className="rp-button subtle"
                      type="button"
                      onClick={() =>
                        handleRemoveFromPlaylist(playlistSlug, item.title)
                      }
                    >
                      Remove
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
          {!playlistLoading && playlistItems.length === 0 && (
            <div className="rp-small-text rp-muted">
              No items yet. Use your playlist tools to add some movies.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default PlaylistsTab;
