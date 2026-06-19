const BASE = import.meta.env.VITE_API_URL || "http://localhost:8001";

async function req(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "API error");
  }
  return res.json();
}

export const api = {
  // Links
  getLinks: (cat) => req(`/api/links${cat ? `?cat=${cat}` : ""}`),
  getLink: (id) => req(`/api/links/${id}`),
  saveLink: (url, customNotes, cat) =>
    req("/api/save-link", {
      method: "POST",
      body: JSON.stringify({ url, custom_notes: customNotes, category_hierarchy: cat }),
    }),
  patchLink: (id, patch) =>
    req(`/api/links/${id}`, {
      method: "PATCH",
      body: JSON.stringify(patch),
    }),
  deleteLink: (id) => req(`/api/links/${id}`, { method: "DELETE" }),

  // Search
  search: (query, topK = 5) =>
    req(`/api/search?query=${encodeURIComponent(query)}&top_k=${topK}`),

  // Stats
  getStats: () => req("/api/stats"),

  // Health
  health: () => req("/health"),
};
