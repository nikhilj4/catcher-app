import React, { useState, useEffect, useContext, createContext, useCallback } from "react";
import {
  Search, Menu, X, Sparkles, Briefcase, CheckSquare, BookOpen, Lightbulb, Heart, Coffee,
  ArrowLeft, SlidersHorizontal, Plus, Settings, Trash2, Star, LogOut, ChevronRight, Pin,
  Clipboard, Check, Copy, MoreHorizontal, RotateCcw, FileText, User, Crown, Mail, Moon, Sun,
  Bell, Shield, Link2, Download, HelpCircle, Info, Palette, Type, Lock, RefreshCw, Eye,
  Globe, ExternalLink, Loader,
} from "lucide-react";
import { api } from "./api.js";

// ---- theme -----------------------------------------------------------------
const LIGHT = { paper: "#FBF8F3", card: "#FFFFFF", ink: "#211C16", sub: "#8A8175", line: "#ECE5D9", shell: "#E9E6F2", hair: "#F2EDE4", dark: false };
const DARK  = { paper: "#191510", card: "#241E18", ink: "#F3EEE6", sub: "#A89E8E", line: "#352D24", shell: "#0D0B08", hair: "#221C16", dark: true };
const ACCENTS = { violet: "#6C5CE7", coral: "#F2664E", emerald: "#16A37B", ocean: "#2E86DE", amber: "#E0900C", rose: "#E84393" };
const ZOOM = { compact: 0.92, default: 1, large: 1.08 };
const hexA = (h, a) => { const n = h.replace("#", ""); const r = parseInt(n.slice(0, 2), 16), g = parseInt(n.slice(2, 4), 16), b = parseInt(n.slice(4, 6), 16); return `rgba(${r},${g},${b},${a})`; };
const ThemeCtx = createContext(null);
const useT = () => useContext(ThemeCtx);

const CATS = {
  work:     { name: "Work",     icon: Briefcase,   bg: "#FFE08A", fg: "#5A4A00" },
  todo:     { name: "To-Do",    icon: CheckSquare, bg: "#FFC7D9", fg: "#7A1F3D" },
  reading:  { name: "Reading",  icon: BookOpen,    bg: "#BFE3F5", fg: "#0E4A63" },
  ideas:    { name: "Ideas",    icon: Lightbulb,   bg: "#C9EAC4", fg: "#1E5226" },
  personal: { name: "Personal", icon: Heart,       bg: "#DDD0F5", fg: "#43306E" },
  daily:    { name: "Daily",    icon: Coffee,      bg: "#FFD2B0", fg: "#7A3A12" },
};
const CAT_IDS = Object.keys(CATS);
const AVATARS = ["#FFD2B0", "#FFC7D9", "#BFE3F5", "#C9EAC4", "#DDD0F5", "#FFE08A"];
const FILTERS = ["All", ...CAT_IDS.map((id) => CATS[id].name)];

const PLATFORM_ICONS = {
  youtube: "🎥", twitter: "🐦", reddit: "🟠", github: "⚡", instagram: "📸",
  tiktok: "🎵", vimeo: "🎬", figma: "🎨", notion: "📝", article: "📰", generic: "🔗",
};

const DEFAULTS = {
  dark: false, accent: "violet", size: "default",
  pinnedFirst: true, sort: "new", groupBy: false, showPreview: true, showDates: true, colorBar: true, compact: false,
  confirmDelete: true, aiSearch: true, spellcheck: true, defaultCat: "ideas",
  notif: { digest: true, reminders: true, mentions: false, sound: true, vibrate: true },
  privacy: { lock: false, hidePreviews: false, analytics: true, biometric: false },
  connected: { drive: false, slack: false, notion: true, calendar: false },
};

// Map a backend link → internal note shape
function linkToNote(link) {
  return {
    id: link.id,
    cat: CAT_IDS.includes(link.cat) ? link.cat : "ideas",
    title: link.title || link.url || "Untitled",
    content: link.ai_summary || link.description || link.url || "",
    url: link.url,
    platform: link.platform || "generic",
    author: link.author,
    ai_tags: link.ai_tags || [],
    thumbnail_url: link.thumbnail_url,
    fav: link.fav || false,
    pin: link.pin || false,
    deleted: link.deleted || false,
    ai_processed: link.ai_processed || false,
    date: link.created_at ? new Date(link.created_at).toLocaleDateString("en-US", { weekday: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }) : "Just now",
  };
}

// ============================================================================
export default function LoomNotes() {
  const [user, setUser] = useState({ name: "Nikhil", email: "nikhil@haystek.co", plan: "Free", bio: "Freelance builder @ Haystek.", avatar: "#FFD2B0" });
  const [notes, setNotes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [backendOnline, setBackendOnline] = useState(false);
  const [settings, setSettings] = useState(DEFAULTS);
  const [stack, setStack] = useState([{ s: "home" }]);
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("All");
  const [menuOpen, setMenuOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const [compose, setCompose] = useState(false);
  const [toast, setToast] = useState("");
  const [confirm, setConfirm] = useState(null);

  const t = { ...(settings.dark ? DARK : LIGHT), ai: ACCENTS[settings.accent], soft: hexA(ACCENTS[settings.accent], settings.dark ? 0.2 : 0.12) };
  const set = (patch) => setSettings((s) => ({ ...s, ...patch }));

  const cur = stack[stack.length - 1];
  const go = (s, p = {}) => setStack((st) => [...st, { s, ...p }]);
  const back = () => setStack((st) => (st.length > 1 ? st.slice(0, -1) : st));
  const home = () => { setStack([{ s: "home" }]); setQuery(""); };
  useEffect(() => { if (!toast) return; const x = setTimeout(() => setToast(""), 2200); return () => clearTimeout(x); }, [toast]);

  // ---- Load links from backend ----
  const loadLinks = useCallback(async () => {
    try {
      const data = await api.getLinks();
      setNotes((data.links || []).map(linkToNote));
      setBackendOnline(true);
    } catch {
      setBackendOnline(false);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadLinks(); }, [loadLinks]);

  // ---- Note helpers ----
  const active = notes.filter((n) => !n.deleted);
  const trashed = notes.filter((n) => n.deleted);
  const countOf = (id) => active.filter((n) => n.cat === id).length;
  const order = (l) => settings.sort === "new" ? l : [...l].reverse();
  const sortList = (l) => settings.pinnedFirst ? [...order(l)].sort((a, b) => Number(b.pin) - Number(a.pin)) : order(l);
  const catNotes = (id) => sortList(active.filter((n) => n.cat === id));
  const favNotes = sortList(active.filter((n) => n.fav));
  const allNotes = sortList(active);
  const byId = (id) => notes.find((n) => n.id === id);

  // Optimistic patch
  const patchLocal = (id, pa) => setNotes((p) => p.map((n) => (n.id === id ? { ...n, ...pa } : n)));

  // ---- SAVE LINK (replace saveNote) ----
  async function saveLink({ url, notes: customNotes, cat }) {
    try {
      const res = await api.saveLink(url, customNotes);
      if (res.status === "already_exists") {
        setToast("Link already saved");
        setCompose(false);
        return;
      }
      // Reload from backend to get new link
      const data = await api.getLinks();
      setNotes((data.links || []).map(linkToNote));
      setCompose(false);
      setToast("Link saved ✓");
      go("category", { cat: cat || "ideas" });
    } catch (e) {
      setToast(`Error: ${e.message}`);
    }
  }

  // ---- PATCH (fav, pin, cat) ----
  async function patchNote(id, pa) {
    patchLocal(id, pa); // optimistic
    try { await api.patchLink(id, pa); } catch {}
  }

  // ---- DELETE ----
  const doDelete = async (id) => {
    patchLocal(id, { deleted: true });
    setToast("Moved to Trash");
    if (cur.s === "note") back();
    try { await api.deleteLink(id); } catch {}
  };
  function softDelete(id) {
    if (settings.confirmDelete) setConfirm({ title: "Delete link?", text: "It will move to Trash.", yes: "Delete", danger: true, onYes: () => doDelete(id) });
    else doDelete(id);
  }
  const restore = (id) => { patchLocal(id, { deleted: false }); setToast("Restored"); };
  const purge = (id) => setConfirm({ title: "Remove forever?", text: "This can't be undone.", yes: "Remove forever", danger: true, onYes: () => { setNotes((p) => p.filter((n) => n.id !== id)); setToast("Removed"); } });
  const clearTrash = () => setConfirm({ title: "Empty trash?", text: `${trashed.length} links will be gone.`, yes: "Empty trash", danger: true, onYes: () => { setNotes((p) => p.filter((n) => !n.deleted)); setToast("Trash emptied"); } });
  const resetApp = () => setConfirm({ title: "Reload links?", text: "Fetch all links fresh from the backend.", yes: "Reload", danger: false, onYes: () => { setLoading(true); loadLinks(); setToast("Reloaded"); home(); } });
  const exportNotes = () => { try { navigator.clipboard.writeText(JSON.stringify(active, null, 2)); } catch {} setToast("Links JSON copied"); };

  // ---- AI SEARCH via backend ----
  async function askAI(q) {
    try {
      const data = await api.search(q, 5);
      const results = data.results || [];
      return {
        summary: data.ai_response || `Searched for "${q}"`,
        sections: results.length ? [{ heading: "Matched Links", points: results.map((r) => `${PLATFORM_ICONS[r.platform] || "🔗"} ${r.title || r.url}`) }] : [],
        related: results.slice(0, 3).map((r) => r.title || r.url),
      };
    } catch {
      return { summary: `Searched for "${q}" — backend offline.`, sections: [], related: [] };
    }
  }

  const showSearch = cur.s === "home" || cur.s === "results";
  const titles = { favorites: "Favorites", trash: "Trash", settings: "Settings", digest: "AI summaries", account: "Account", upgrade: "Upgrade", all: "All links", notif: "Notifications", privacy: "Privacy & security", connected: "Connected apps", help: "Help & support", about: "About" };
  const defCat = cur.cat || settings.defaultCat;

  return (
    <ThemeCtx.Provider value={t}>
    <div style={{ background: t.paper, minHeight: "100vh", fontFamily: "'Outfit',sans-serif", transition: "background .3s", color: t.ink }}>
      <style>{`@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,600;9..144,700&family=Outfit:wght@300;400;500;600&display=swap');
        .disp{font-family:'Fraunces',serif} .ln-scroll::-webkit-scrollbar{width:4px} .ln-scroll::-webkit-scrollbar-thumb{background:rgba(0,0,0,.12);border-radius:99px}
        @keyframes ln-rise{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:none}} .ln-rise{animation:ln-rise .3s ease both}
        @keyframes ln-pulse{0%,100%{opacity:.4}50%{opacity:1}} .ln-dot{animation:ln-pulse 1s ease-in-out infinite}
        @keyframes spin{from{transform:rotate(0deg)}to{transform:rotate(360deg)}} .spinning{animation:spin 1s linear infinite}
        textarea,input{font-family:inherit}
        *{box-sizing:border-box}`}</style>

      <div style={{ maxWidth: 680, margin: "0 auto", minHeight: "100vh", background: t.paper, position: "relative", display: "flex", flexDirection: "column", transition: "background .3s,color .3s", boxShadow: "0 0 60px rgba(0,0,0,.07)" }}>

        {/* Backend status pill — fixed top-right within layout */}
        <div style={{ position: "absolute", top: 30, right: 28, zIndex: 45, display: "flex", alignItems: "center", gap: 4, background: backendOnline ? "#16A37B22" : "#F2664E22", borderRadius: 99, padding: "4px 10px" }}>
          <div style={{ width: 6, height: 6, borderRadius: 99, background: backendOnline ? "#16A37B" : "#F2664E" }} />
          <span style={{ fontSize: 11, fontWeight: 600, color: backendOnline ? "#16A37B" : "#F2664E" }}>{backendOnline ? "API" : "Offline"}</span>
        </div>

        {cur.s === "loggedout" ? <LoggedOut user={user} onLogin={home} /> : (
          <>
            <div style={{ flex: 1, display: "flex", flexDirection: "column", minHeight: 0, zoom: ZOOM[settings.size] }}>
              {/* TOP BAR */}
              <div style={{ padding: "28px 28px 0", flexShrink: 0 }}>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                  {stack.length > 1 ? <button onClick={back} style={iconBtn(t)}><ArrowLeft size={20} strokeWidth={2.2} /></button>
                    : <button onClick={() => setMenuOpen(true)} style={iconBtn(t)}><Menu size={20} strokeWidth={2.2} /></button>}
                  {cur.s === "home" ? <div style={{ fontSize: 12, color: t.sub, letterSpacing: ".06em", flex: 1, textAlign: "center" }}>{new Date().toLocaleDateString("en-US", { weekday: "long", month: "short", day: "numeric" }).toUpperCase()}</div>
                    : <div className="disp" style={{ fontSize: 17, fontWeight: 600, flex: 1, textAlign: "center" }}>{cur.s === "category" ? CATS[cur.cat]?.name : cur.s === "note" ? "Link" : titles[cur.s] || ""}</div>}
                  <button onClick={() => setProfileOpen(true)} style={{ ...iconBtn(t), padding: 0, overflow: "hidden", background: user.avatar }}>
                    <div style={{ width: "100%", height: "100%", display: "grid", placeItems: "center", fontWeight: 600, color: "#5a3a1a" }}>{user.name[0].toUpperCase()}</div></button>
                </div>
                {cur.s === "home" && <div className="ln-rise" style={{ marginTop: 16 }}>
                  <h1 className="disp" style={{ fontSize: 34, fontWeight: 600, lineHeight: 1.05, margin: 0 }}>Hey, {user.name}.</h1>
                  <p style={{ color: t.sub, fontSize: 15, margin: "6px 0 0" }}>Save links. Search with AI. Stay organised.</p></div>}
                {showSearch && <div style={{ marginTop: cur.s === "home" ? 18 : 12, display: "flex", alignItems: "center", gap: 10, background: t.card, border: `1.5px solid ${query ? t.ai : t.line}`, borderRadius: 18, padding: "13px 14px" }}>
                  <Sparkles size={18} color={t.ai} strokeWidth={2.2} />
                  <input value={query} onChange={(e) => setQuery(e.target.value)} onKeyDown={(e) => e.key === "Enter" && query.trim() && go("results", { q: query.trim() })} placeholder="Ask or search your saved links…"
                    style={{ border: "none", outline: "none", flex: 1, fontSize: 15, color: t.ink, background: "transparent" }} />
                  {query && <button onClick={() => query.trim() && go("results", { q: query.trim() })} style={{ border: "none", background: t.ai, color: "#fff", borderRadius: 12, width: 32, height: 32, display: "grid", placeItems: "center", cursor: "pointer" }}><Search size={16} strokeWidth={2.5} /></button>}
                </div>}
              </div>

              {/* BODY */}
              <div className="ln-scroll" style={{ flex: 1, overflowY: "auto", padding: "16px 28px 100px" }}>
                {loading && <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 12, paddingTop: 40, color: t.sub }}>
                  <Loader size={28} strokeWidth={2} className="spinning" color={t.ai} />
                  <div style={{ fontSize: 14 }}>Loading your vault…</div>
                </div>}
                {!loading && cur.s === "home" && <Home t={t} filter={filter} setFilter={setFilter} countOf={countOf} go={go} backendOnline={backendOnline} />}
                {cur.s === "results" && <AnswerView fetcher={() => askAI(cur.q)} label={`ANSWER FOR "${cur.q.toUpperCase()}"`} dep={cur.q} />}
                {cur.s === "category" && <NoteList meta={CATS[cur.cat]} notes={catNotes(cur.cat)} settings={settings} onOpen={(id) => go("note", { id, cat: cur.cat })} onFav={(id, v) => patchNote(id, { fav: v })} onPin={(id, v) => patchNote(id, { pin: v })} onDelete={softDelete} onNew={() => setCompose(true)} />}
                {cur.s === "favorites" && <NoteList meta={{ name: "Favorites", icon: Star, bg: "#FFE08A", fg: "#5A4A00" }} notes={favNotes} settings={settings} onOpen={(id) => go("note", { id })} onFav={(id, v) => patchNote(id, { fav: v })} onPin={(id, v) => patchNote(id, { pin: v })} onDelete={softDelete} empty="No favorites yet. Star a link to keep it here." />}
                {cur.s === "all" && <NoteList meta={{ name: "All links", icon: Link2, bg: "#DDD0F5", fg: "#43306E" }} notes={allNotes} settings={settings} group={settings.groupBy} onOpen={(id) => go("note", { id })} onFav={(id, v) => patchNote(id, { fav: v })} onPin={(id, v) => patchNote(id, { pin: v })} onDelete={softDelete} />}
                {cur.s === "trash" && <TrashList notes={trashed} onRestore={restore} onPurge={purge} onClear={clearTrash} />}
                {cur.s === "note" && byId(cur.id) && <NoteDetail note={byId(cur.id)} settings={settings} onPatch={(pa) => patchNote(cur.id, pa)} onDelete={() => softDelete(cur.id)} onCopy={() => { try { navigator.clipboard.writeText(byId(cur.id).url || byId(cur.id).content); } catch {} setToast("Copied"); }} />}
                {cur.s === "settings" && <SettingsView settings={settings} set={set} stats={{ active: active.length, fav: favNotes.length, trash: trashed.length }} go={go} onExport={exportNotes} onClearTrash={clearTrash} onReset={resetApp} />}
                {cur.s === "account" && <AccountView user={user} onSave={(u) => { setUser(u); setToast("Saved"); }} onUpgrade={() => go("upgrade")} />}
                {cur.s === "upgrade" && <UpgradeView plan={user.plan} onPick={(plan) => { setUser((u) => ({ ...u, plan })); setToast(plan === "Pro" ? "You're on Pro 🎉" : "Switched to Free"); }} />}
                {cur.s === "notif" && <ToggleScreen icon={Bell} groups={[{ title: "Push", rows: [["digest", "Daily digest", "A morning summary of your links"], ["reminders", "Reminders", "Nudge me about pinned links"], ["mentions", "Mentions", "When someone tags me"]] }, { title: "Sound", rows: [["sound", "Sounds", "Play a chime on alerts"], ["vibrate", "Vibrate", "Haptic feedback"]] }]} state={settings.notif} onToggle={(k) => set({ notif: { ...settings.notif, [k]: !settings.notif[k] } })} />}
                {cur.s === "privacy" && <ToggleScreen icon={Shield} groups={[{ title: "App security", rows: [["lock", "App lock", "Require a passcode to open"], ["biometric", "Face / fingerprint", "Unlock with biometrics"]] }, { title: "Privacy", rows: [["hidePreviews", "Hide previews", "Blur content in the app switcher"], ["analytics", "Usage analytics", "Share anonymous usage data"]] }]} state={settings.privacy} onToggle={(k) => set({ privacy: { ...settings.privacy, [k]: !settings.privacy[k] } })} />}
                {cur.s === "connected" && <ConnectedView state={settings.connected} onToggle={(k) => set({ connected: { ...settings.connected, [k]: !settings.connected[k] } })} />}
                {cur.s === "help" && <HelpView />}
                {cur.s === "about" && <AboutView onToast={setToast} backendOnline={backendOnline} />}
              </div>
            </div>

            {(cur.s === "home" || cur.s === "category") && <button onClick={() => setCompose(true)} style={{ position: "fixed", bottom: 32, right: "max(28px, calc(50% - 312px))", width: 58, height: 58, borderRadius: 20, background: t.ink, color: t.paper, border: "none", cursor: "pointer", display: "grid", placeItems: "center", boxShadow: "0 12px 28px -8px rgba(0,0,0,.5)", zIndex: 30 }}><Plus size={26} strokeWidth={2.4} /></button>}
          </>
        )}

        {toast && <div className="ln-rise" style={{ position: "fixed", bottom: 32, left: "50%", transform: "translateX(-50%)", background: t.ink, color: t.paper, padding: "11px 18px", borderRadius: 14, fontSize: 14, fontWeight: 500, zIndex: 95, display: "flex", alignItems: "center", gap: 8, whiteSpace: "nowrap" }}><Check size={16} strokeWidth={2.6} color="#5ec77a" /> {toast}</div>}

        {confirm && <ConfirmModal {...confirm} onClose={() => setConfirm(null)} />}
        <ComposeSheet open={compose} onClose={() => setCompose(false)} onSave={saveLink} defaultCat={defCat} spellcheck={settings.spellcheck} />

        {/* MENU */}
        <Overlay open={menuOpen} onClose={() => setMenuOpen(false)} side="left">
          <div className="disp" style={{ fontSize: 24, fontWeight: 600, marginBottom: 4 }}>Knowledge Vault</div>
          <div style={{ color: t.sub, fontSize: 13, marginBottom: 18 }}>{active.length} links · 6 categories</div>
          {[{ icon: Link2, label: "All links", go: "all" }, { icon: Star, label: "Favorites", go: "favorites" }, { icon: Sparkles, label: "AI search", go: "results", q: "what did I save?" }, { icon: Trash2, label: "Trash", go: "trash", badge: trashed.length || null }, { icon: Bell, label: "Notifications", go: "notif" }, { icon: Link2, label: "Connected apps", go: "connected" }, { icon: Settings, label: "Settings", go: "settings" }, { icon: HelpCircle, label: "Help & support", go: "help" }, { icon: Info, label: "About", go: "about" }].map((m, i) => {
            const Icon = m.icon; return <button key={i} onClick={() => { setMenuOpen(false); go(m.go, m.q ? { q: m.q } : {}); }} style={menuRow(t)}>
              <span style={{ display: "flex", alignItems: "center", gap: 12 }}><Icon size={19} strokeWidth={2.1} /> {m.label}</span>
              <span style={{ display: "flex", alignItems: "center", gap: 8 }}>{m.badge ? <span style={{ background: t.hair, color: t.sub, fontSize: 12, fontWeight: 700, borderRadius: 99, padding: "1px 8px" }}>{m.badge}</span> : null}<ChevronRight size={17} color={t.sub} /></span></button>;
          })}
        </Overlay>

        {/* PROFILE */}
        <Overlay open={profileOpen} onClose={() => setProfileOpen(false)} side="right">
          <div style={{ textAlign: "center", marginBottom: 16 }}>
            <div style={{ width: 64, height: 64, borderRadius: 22, background: user.avatar, display: "grid", placeItems: "center", margin: "0 auto", fontSize: 26, fontWeight: 600, color: "#5a3a1a" }}>{user.name[0].toUpperCase()}</div>
            <div className="disp" style={{ fontSize: 20, fontWeight: 600, marginTop: 10 }}>{user.name}</div>
            <div style={{ color: t.sub, fontSize: 13, display: "flex", alignItems: "center", justifyContent: "center", gap: 6 }}>{user.plan} plan {user.plan === "Pro" && <Crown size={14} color="#C99700" fill="#FFD75A" />}</div>
          </div>
          {[{ icon: User, label: "Account", go: "account" }, { icon: Crown, label: user.plan === "Pro" ? "Manage plan" : "Upgrade to Pro", go: "upgrade" }, { icon: Bell, label: "Notifications", go: "notif" }, { icon: Palette, label: "Appearance", go: "settings" }, { icon: Shield, label: "Privacy & security", go: "privacy" }, { icon: Link2, label: "Connected apps", go: "connected" }, { icon: Download, label: "Export links", export: true }, { icon: HelpCircle, label: "Help & support", go: "help" }, { icon: Info, label: "About", go: "about" }].map((m, i) => {
            const Icon = m.icon; return <button key={i} onClick={() => { setProfileOpen(false); m.export ? exportNotes() : go(m.go); }} style={menuRow(t)}>
              <span style={{ display: "flex", alignItems: "center", gap: 12 }}><Icon size={19} strokeWidth={2.1} /> {m.label}</span><ChevronRight size={17} color={t.sub} /></button>;
          })}
          <button onClick={() => { setProfileOpen(false); setStack([{ s: "loggedout" }]); }} style={{ ...menuRow(t), color: "#d05a48" }}>
            <span style={{ display: "flex", alignItems: "center", gap: 12 }}><LogOut size={19} strokeWidth={2.1} /> Log out</span></button>
        </Overlay>
      </div>
    </div>
    </ThemeCtx.Provider>
  );
}

// ---- HOME ------------------------------------------------------------------
function Home({ t, filter, setFilter, countOf, go, backendOnline }) {
  return (
    <div className="ln-rise">
      <div style={{ display: "flex", gap: 8, overflowX: "auto", paddingBottom: 4 }} className="ln-scroll">
        <span style={{ ...filterPill(t, false), padding: "8px 12px", display: "inline-flex" }}><SlidersHorizontal size={15} strokeWidth={2.2} /></span>
        {FILTERS.map((f) => <button key={f} onClick={() => setFilter(f)} style={filterPill(t, filter === f)}>{f}</button>)}
      </div>
      {!backendOnline && <div style={{ marginTop: 14, background: "#F2664E18", border: "1px solid #F2664E44", borderRadius: 14, padding: "12px 14px", fontSize: 13, color: "#d05a48", display: "flex", alignItems: "center", gap: 8 }}>
        <Globe size={15} strokeWidth={2.4} /> Backend offline — start <code style={{ background: "#F2664E22", borderRadius: 6, padding: "1px 6px" }}>dev_server.py</code> to connect
      </div>}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14, marginTop: 18 }}>
        {(filter === "All" ? CAT_IDS : CAT_IDS.filter((id) => CATS[id].name === filter)).map((id) => {
          const c = CATS[id]; const Icon = c.icon;
          return <button key={id} onClick={() => go("category", { cat: id })} style={{ aspectRatio: "1/1", background: c.bg, borderRadius: 24, padding: 16, position: "relative", overflow: "hidden", cursor: "pointer", border: "none", textAlign: "left", display: "flex", flexDirection: "column", justifyContent: "space-between", boxShadow: "0 8px 20px -8px rgba(0,0,0,.18)" }}>
            <div style={{ position: "absolute", top: 0, right: 0, width: 0, height: 0, borderTop: "26px solid rgba(255,255,255,.45)", borderLeft: "26px solid transparent" }} />
            <div style={{ width: 42, height: 42, borderRadius: 14, background: "rgba(255,255,255,.55)", display: "grid", placeItems: "center" }}><Icon size={20} color={c.fg} strokeWidth={2.2} /></div>
            <div><div className="disp" style={{ fontSize: 20, fontWeight: 600, color: c.fg }}>{c.name}</div><div style={{ fontSize: 13, color: c.fg, opacity: .7, marginTop: 2 }}>{countOf(id)} {countOf(id) === 1 ? "link" : "links"}</div></div></button>;
        })}
      </div>
    </div>
  );
}

// ---- ANSWER ----------------------------------------------------------------
function AnswerView({ fetcher, label, dep }) {
  const t = useT(); const [data, setData] = useState(null);
  useEffect(() => { let on = true; setData(null); fetcher().then((d) => on && setData(d)); return () => { on = false; }; }, [dep]);
  if (!data) return <div className="ln-rise" style={{ paddingTop: 4 }}>
    <div style={{ display: "flex", alignItems: "center", gap: 8, color: t.ai, fontWeight: 500 }}><Sparkles size={18} strokeWidth={2.2} /> Searching<span className="ln-dot">•</span><span className="ln-dot" style={{ animationDelay: ".2s" }}>•</span><span className="ln-dot" style={{ animationDelay: ".4s" }}>•</span></div>
    {[1, 2, 3].map((i) => <div key={i} style={{ height: 14, background: t.line, borderRadius: 8, marginTop: 14, width: `${100 - i * 12}%` }} />)}</div>;
  return <div className="ln-rise">
    <div style={{ fontSize: 12, color: t.sub, letterSpacing: ".06em", marginBottom: 8 }}>{label}</div>
    <div style={{ background: t.soft, borderRadius: 18, padding: 16, borderLeft: `3px solid ${t.ai}` }}><p style={{ margin: 0, fontSize: 15, lineHeight: 1.5 }}>{data.summary}</p></div>
    {(data.sections || []).map((s, i) => <div key={i} style={{ background: t.card, border: `1px solid ${t.line}`, borderRadius: 18, padding: 16, marginTop: 12 }}>
      <div className="disp" style={{ fontSize: 17, fontWeight: 600, marginBottom: 8 }}>{s.heading}</div>
      {(s.points || []).map((p, j) => <div key={j} style={{ display: "flex", gap: 10, padding: "6px 0", borderTop: j ? `1px solid ${t.line}` : "none" }}><span style={{ color: t.ai, fontWeight: 700 }}>›</span><span style={{ fontSize: 14, lineHeight: 1.45, color: t.ink, opacity: .85 }}>{p}</span></div>)}</div>)}
    {data.related?.length > 0 && <div style={{ marginTop: 16 }}><div style={{ fontSize: 13, color: t.sub, marginBottom: 8 }}>Related</div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>{data.related.map((r, i) => <span key={i} style={{ background: t.card, border: `1px solid ${t.line}`, borderRadius: 999, padding: "7px 12px", fontSize: 13 }}>{r}</span>)}</div></div>}
  </div>;
}

// ---- NOTE LIST -------------------------------------------------------------
function NoteList({ meta, notes, settings, group, onOpen, onFav, onPin, onDelete, onNew, empty }) {
  const t = useT(); const Icon = meta.icon;
  const groups = group ? CAT_IDS.map((id) => ({ id, items: notes.filter((n) => n.cat === id) })).filter((g) => g.items.length) : null;
  return <div className="ln-rise">
    <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 16 }}>
      <div style={{ width: 46, height: 46, borderRadius: 16, background: meta.bg, display: "grid", placeItems: "center" }}><Icon size={22} color={meta.fg} strokeWidth={2.2} /></div>
      <div><h2 className="disp" style={{ fontSize: 26, fontWeight: 600, margin: 0 }}>{meta.name}</h2><div style={{ color: t.sub, fontSize: 13 }}>{notes.length} {notes.length === 1 ? "link" : "links"}</div></div></div>
    {onNew && <button onClick={onNew} style={{ width: "100%", display: "flex", alignItems: "center", gap: 10, background: t.card, border: `1.5px dashed ${t.line}`, borderRadius: 16, padding: "13px 16px", color: t.sub, fontSize: 14, cursor: "pointer", marginBottom: 14, fontWeight: 500 }}><Plus size={18} strokeWidth={2.4} /> Save a link to {meta.name}</button>}
    {notes.length === 0 && <div style={{ textAlign: "center", padding: "40px 10px", color: t.sub, fontSize: 14 }}>{empty || "Nothing here yet. Tap + to save a link."}</div>}
    {groups ? groups.map((g) => <div key={g.id} style={{ marginBottom: 18 }}>
      <div style={{ fontSize: 12, fontWeight: 700, letterSpacing: ".05em", color: CATS[g.id].fg, background: CATS[g.id].bg, display: "inline-block", padding: "3px 10px", borderRadius: 8, marginBottom: 10 }}>{CATS[g.id].name.toUpperCase()}</div>
      <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>{g.items.map((n) => <NoteRow key={n.id} n={n} settings={settings} onOpen={() => onOpen(n.id)} onFav={() => onFav(n.id, !n.fav)} onPin={() => onPin(n.id, !n.pin)} onDelete={() => onDelete(n.id)} />)}</div></div>)
      : <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>{notes.map((n) => <NoteRow key={n.id} n={n} settings={settings} onOpen={() => onOpen(n.id)} onFav={() => onFav(n.id, !n.fav)} onPin={() => onPin(n.id, !n.pin)} onDelete={() => onDelete(n.id)} />)}</div>}
  </div>;
}

function NoteRow({ n, settings, onOpen, onFav, onPin, onDelete }) {
  const t = useT(); const c = CATS[n.cat] || CATS.ideas; const [open, setOpen] = useState(false);
  const pad = settings.compact ? 12 : 16;
  return <div style={{ background: t.card, border: `1px solid ${t.line}`, borderRadius: 18, overflow: "hidden" }}>
    <div onClick={onOpen} style={{ padding: pad, cursor: "pointer", borderLeft: settings.colorBar ? `4px solid ${c.bg}` : "none" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 8 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 6, flex: 1, minWidth: 0 }}>
          <span style={{ fontSize: 14, flexShrink: 0 }}>{PLATFORM_ICONS[n.platform] || "🔗"}</span>
          <div className="disp" style={{ fontSize: 16, fontWeight: 600, lineHeight: 1.2, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{n.pin && <Pin size={13} strokeWidth={2.4} style={{ marginRight: 4, color: t.ai }} />}{n.title}</div>
        </div>
        {onFav && <button onClick={(e) => { e.stopPropagation(); setOpen((o) => !o); }} style={{ border: "none", background: "transparent", cursor: "pointer", color: t.sub, padding: 2, flexShrink: 0 }}><MoreHorizontal size={18} /></button>}
      </div>
      {settings.showPreview && <p style={{ margin: "6px 0 0", fontSize: 13.5, color: t.sub, lineHeight: 1.45, display: "-webkit-box", WebkitLineClamp: settings.compact ? 1 : 2, WebkitBoxOrient: "vertical", overflow: "hidden" }}>{n.content}</p>}
      {!n.ai_processed && <div style={{ marginTop: 6, fontSize: 11, color: t.ai, display: "flex", alignItems: "center", gap: 4 }}><Loader size={11} className="spinning" /> AI enriching…</div>}
      {settings.showDates && <div style={{ fontSize: 12, color: t.sub, marginTop: 6, opacity: .8 }}>{n.date}</div>}
    </div>
    {open && onFav && <div style={{ display: "flex", borderTop: `1px solid ${t.line}` }}>
      <RowAct icon={Star} label={n.fav ? "Unfav" : "Favorite"} active={n.fav} onClick={onFav} />
      <RowAct icon={Pin} label={n.pin ? "Unpin" : "Pin"} active={n.pin} onClick={onPin} />
      <RowAct icon={Trash2} label="Delete" danger onClick={onDelete} /></div>}
  </div>;
}

function RowAct({ icon: Icon, label, active, danger, onClick }) {
  const t = useT();
  return <button onClick={onClick} style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", gap: 4, padding: "11px 0", border: "none", background: "transparent", cursor: "pointer", fontSize: 12, fontWeight: 500, color: danger ? "#d05a48" : active ? t.ai : t.sub, borderLeft: `1px solid ${t.line}` }}><Icon size={17} strokeWidth={2.2} fill={active && !danger ? t.ai : "none"} /> {label}</button>;
}

// ---- TRASH -----------------------------------------------------------------
function TrashList({ notes, onRestore, onPurge, onClear }) {
  const t = useT();
  return <div className="ln-rise">
    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <div style={{ width: 46, height: 46, borderRadius: 16, background: t.hair, display: "grid", placeItems: "center" }}><Trash2 size={22} color={t.sub} strokeWidth={2.2} /></div>
        <div><h2 className="disp" style={{ fontSize: 26, fontWeight: 600, margin: 0 }}>Trash</h2><div style={{ color: t.sub, fontSize: 13 }}>{notes.length} deleted</div></div></div>
      {notes.length > 0 && <button onClick={onClear} style={{ border: `1.5px solid ${t.line}`, background: t.card, color: "#d05a48", borderRadius: 12, padding: "8px 12px", fontSize: 13, fontWeight: 600, cursor: "pointer" }}>Empty</button>}
    </div>
    {notes.length === 0 && <div style={{ textAlign: "center", padding: "40px 10px", color: t.sub, fontSize: 14 }}>Trash is empty.</div>}
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>{notes.map((n) => <div key={n.id} style={{ background: t.card, border: `1px solid ${t.line}`, borderRadius: 18, padding: 16 }}>
      <div className="disp" style={{ fontSize: 16, fontWeight: 600, opacity: .85 }}>{PLATFORM_ICONS[n.platform] || "🔗"} {n.title}</div>
      <div style={{ fontSize: 12, color: t.sub, margin: "4px 0 12px" }}>{(CATS[n.cat] || CATS.ideas).name} · {n.date}</div>
      <div style={{ display: "flex", gap: 10 }}>
        <button onClick={() => onRestore(n.id)} style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", gap: 6, border: `1.5px solid ${t.line}`, background: t.card, borderRadius: 12, padding: "9px", fontSize: 13, fontWeight: 600, cursor: "pointer", color: t.ink }}><RotateCcw size={15} strokeWidth={2.3} /> Restore</button>
        <button onClick={() => onPurge(n.id)} style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", gap: 6, border: "1.5px solid #e8c0b8", background: t.card, borderRadius: 12, padding: "9px", fontSize: 13, fontWeight: 600, cursor: "pointer", color: "#d05a48" }}><Trash2 size={15} strokeWidth={2.3} /> Remove</button>
      </div></div>)}</div>
  </div>;
}

// ---- NOTE DETAIL -----------------------------------------------------------
function NoteDetail({ note, settings, onPatch, onDelete, onCopy }) {
  const t = useT(); const c = CATS[note.cat] || CATS.ideas;
  return <div className="ln-rise">
    <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
      <span style={{ background: c.bg, color: c.fg, fontSize: 12, fontWeight: 600, borderRadius: 999, padding: "5px 12px" }}>{c.name}</span>
      <span style={{ fontSize: 13, background: t.hair, color: t.sub, borderRadius: 99, padding: "4px 10px" }}>{PLATFORM_ICONS[note.platform] || "🔗"} {note.platform || "link"}</span>
    </div>
    <div className="disp" style={{ fontSize: 24, fontWeight: 600, lineHeight: 1.2, marginBottom: 8 }}>{note.title}</div>

    {/* URL bar */}
    {note.url && <a href={note.url} target="_blank" rel="noopener noreferrer" style={{ display: "flex", alignItems: "center", gap: 8, background: t.card, border: `1px solid ${t.line}`, borderRadius: 12, padding: "10px 12px", marginBottom: 14, textDecoration: "none", color: t.ai, fontSize: 13, fontWeight: 500, overflow: "hidden" }}>
      <ExternalLink size={14} strokeWidth={2.3} style={{ flexShrink: 0 }} />
      <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{note.url}</span>
    </a>}

    {/* AI summary */}
    {note.content && <div style={{ background: t.soft, borderRadius: 16, padding: "14px 16px", marginBottom: 14, borderLeft: `3px solid ${t.ai}` }}>
      <div style={{ fontSize: 11, color: t.ai, fontWeight: 700, letterSpacing: ".06em", marginBottom: 6 }}>AI SUMMARY</div>
      <p style={{ margin: 0, fontSize: 14.5, lineHeight: 1.55, color: t.ink, opacity: .9 }}>{note.content}</p>
    </div>}

    {/* Tags */}
    {note.ai_tags?.length > 0 && <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 14 }}>
      {note.ai_tags.map((tag, i) => <span key={i} style={{ background: t.hair, color: t.sub, borderRadius: 99, padding: "5px 10px", fontSize: 12, fontWeight: 500 }}>#{tag}</span>)}
    </div>}

    {!note.ai_processed && <div style={{ fontSize: 12, color: t.ai, display: "flex", alignItems: "center", gap: 5, marginBottom: 14 }}><Loader size={12} className="spinning" /> AI enrichment in progress…</div>}

    <div style={{ display: "flex", gap: 10, marginTop: 4 }}>
      <ActBtn icon={Star} label={note.fav ? "Favorited" : "Favorite"} active={note.fav} onClick={() => onPatch({ fav: !note.fav })} />
      <ActBtn icon={Pin} label={note.pin ? "Pinned" : "Pin"} active={note.pin} onClick={() => onPatch({ pin: !note.pin })} />
      <ActBtn icon={Copy} label="Copy URL" onClick={onCopy} />
      <ActBtn icon={Trash2} label="Delete" danger onClick={onDelete} /></div>
  </div>;
}

function ActBtn({ icon: Icon, label, active, danger, onClick }) {
  const t = useT();
  return <button onClick={onClick} style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", gap: 5, padding: "12px 4px", borderRadius: 16, cursor: "pointer", fontSize: 12, fontWeight: 500, border: `1.5px solid ${danger ? "#e8c0b8" : active ? t.ai : t.line}`, background: active ? t.soft : t.card, color: danger ? "#d05a48" : active ? t.ai : t.ink }}><Icon size={18} strokeWidth={2.2} fill={active && !danger ? t.ai : "none"} /> {label}</button>;
}

// ---- reusable rows ---------------------------------------------------------
function Toggle({ on, onClick }) {
  const t = useT();
  return <button onClick={onClick} style={{ width: 48, height: 28, borderRadius: 99, border: "none", cursor: "pointer", background: on ? t.ai : (t.dark ? "#4a4036" : "#d8d1c5"), position: "relative", transition: "background .2s", flexShrink: 0 }}>
    <span style={{ position: "absolute", top: 3, left: on ? 23 : 3, width: 22, height: 22, borderRadius: 99, background: "#fff", transition: "left .2s" }} /></button>;
}
function Section({ children }) { const t = useT(); return <div className="disp" style={{ fontSize: 16, fontWeight: 600, margin: "22px 0 2px", color: t.ink }}>{children}</div>; }
function Row({ title, desc, children }) {
  const t = useT();
  return <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, padding: "13px 0", borderTop: `1px solid ${t.line}` }}>
    <div><div style={{ fontSize: 15, fontWeight: 500 }}>{title}</div>{desc && <div style={{ fontSize: 12.5, color: t.sub, marginTop: 2 }}>{desc}</div>}</div>{children}</div>;
}
function Seg({ options, value, onChange }) {
  const t = useT();
  return <div style={{ display: "flex", background: t.hair, borderRadius: 12, padding: 3, gap: 3 }}>
    {options.map((o) => <button key={o.v} onClick={() => onChange(o.v)} style={{ border: "none", cursor: "pointer", borderRadius: 9, padding: "6px 12px", fontSize: 13, fontWeight: 600, background: value === o.v ? t.card : "transparent", color: value === o.v ? t.ink : t.sub, boxShadow: value === o.v ? "0 1px 4px rgba(0,0,0,.1)" : "none" }}>{o.label}</button>)}</div>;
}
function LinkRow({ icon: Icon, label, desc, onClick, danger }) {
  const t = useT();
  return <button onClick={onClick} style={{ width: "100%", display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, padding: "13px 0", borderTop: `1px solid ${t.line}`, background: "transparent", border: "none", borderTopWidth: 1, cursor: "pointer", color: danger ? "#d05a48" : t.ink, textAlign: "left" }}>
    <span style={{ display: "flex", alignItems: "center", gap: 12 }}>{Icon && <Icon size={19} strokeWidth={2.1} />}<span><span style={{ fontSize: 15, fontWeight: 500 }}>{label}</span>{desc && <span style={{ display: "block", fontSize: 12.5, color: t.sub, marginTop: 2 }}>{desc}</span>}</span></span>
    <ChevronRight size={17} color={t.sub} /></button>;
}

// ---- SETTINGS --------------------------------------------------------------
function SettingsView({ settings, set, stats, go, onExport, onClearTrash, onReset }) {
  const t = useT();
  return <div className="ln-rise">
    <div style={{ display: "flex", gap: 10 }}>
      {[["Saved", stats.active], ["Favorites", stats.fav], ["Trash", stats.trash]].map(([l, v]) => <div key={l} style={{ flex: 1, background: t.card, border: `1px solid ${t.line}`, borderRadius: 16, padding: "14px 10px", textAlign: "center" }}><div className="disp" style={{ fontSize: 24, fontWeight: 600 }}>{v}</div><div style={{ fontSize: 12, color: t.sub }}>{l}</div></div>)}
    </div>
    <Section>Appearance</Section>
    <Row title="Dark mode" desc="Easy on the eyes at night"><Toggle on={settings.dark} onClick={() => set({ dark: !settings.dark })} /></Row>
    <Row title="Accent color" desc="Used across buttons and highlights">
      <div style={{ display: "flex", gap: 8 }}>{Object.entries(ACCENTS).map(([k, hex]) => <button key={k} onClick={() => set({ accent: k })} style={{ width: 24, height: 24, borderRadius: 99, background: hex, border: settings.accent === k ? `2.5px solid ${t.ink}` : "2.5px solid transparent", cursor: "pointer" }} />)}</div></Row>
    <Row title="Display size" desc="Scale the whole interface"><Seg options={[{ v: "compact", label: "S" }, { v: "default", label: "M" }, { v: "large", label: "L" }]} value={settings.size} onChange={(v) => set({ size: v })} /></Row>
    <Section>Links & lists</Section>
    <Row title="Pinned first" desc="Float pinned links to the top"><Toggle on={settings.pinnedFirst} onClick={() => set({ pinnedFirst: !settings.pinnedFirst })} /></Row>
    <Row title="Sort order"><Seg options={[{ v: "new", label: "Newest" }, { v: "old", label: "Oldest" }]} value={settings.sort} onChange={(v) => set({ sort: v })} /></Row>
    <Row title="Group by category" desc="In the All links view"><Toggle on={settings.groupBy} onClick={() => set({ groupBy: !settings.groupBy })} /></Row>
    <Row title="Show previews" desc="Two lines of AI summary per link"><Toggle on={settings.showPreview} onClick={() => set({ showPreview: !settings.showPreview })} /></Row>
    <Row title="Show dates"><Toggle on={settings.showDates} onClick={() => set({ showDates: !settings.showDates })} /></Row>
    <Row title="Color bar" desc="Category stripe on each row"><Toggle on={settings.colorBar} onClick={() => set({ colorBar: !settings.colorBar })} /></Row>
    <Row title="Compact rows"><Toggle on={settings.compact} onClick={() => set({ compact: !settings.compact })} /></Row>
    <Section>Behavior</Section>
    <Row title="AI search" desc="Search your vault via backend AI"><Toggle on={settings.aiSearch} onClick={() => set({ aiSearch: !settings.aiSearch })} /></Row>
    <Row title="Confirm before delete"><Toggle on={settings.confirmDelete} onClick={() => set({ confirmDelete: !settings.confirmDelete })} /></Row>
    <Section>Privacy & connections</Section>
    <LinkRow icon={Shield} label="Privacy & security" onClick={() => go("privacy")} />
    <LinkRow icon={Bell} label="Notifications" onClick={() => go("notif")} />
    <LinkRow icon={Link2} label="Connected apps" onClick={() => go("connected")} />
    <Section>Data</Section>
    <LinkRow icon={Download} label="Export links" desc="Copy all links as JSON" onClick={onExport} />
    <LinkRow icon={Trash2} label="Empty trash" onClick={onClearTrash} />
    <LinkRow icon={RefreshCw} label="Reload from API" desc="Fetch all links fresh from the backend" onClick={onReset} danger />
    <Section>About</Section>
    <LinkRow icon={HelpCircle} label="Help & support" onClick={() => go("help")} />
    <LinkRow icon={Info} label="About Knowledge Vault" onClick={() => go("about")} />
    <div style={{ marginTop: 22, textAlign: "center", color: t.sub, fontSize: 12 }}>Knowledge Vault · v1.0 · made with Haystek</div>
  </div>;
}

function ToggleScreen({ icon: Icon, groups, state, onToggle }) {
  const t = useT();
  return <div className="ln-rise">
    <div style={{ width: 52, height: 52, borderRadius: 16, background: t.soft, display: "grid", placeItems: "center", marginBottom: 14 }}><Icon size={24} color={t.ai} strokeWidth={2.1} /></div>
    {groups.map((g, gi) => <div key={gi}><Section>{g.title}</Section>{g.rows.map(([k, title, desc]) => <Row key={k} title={title} desc={desc}><Toggle on={state[k]} onClick={() => onToggle(k)} /></Row>)}</div>)}
  </div>;
}

function ConnectedView({ state, onToggle }) {
  const t = useT();
  const apps = [["drive", "Google Drive", "Back up links to Drive"], ["slack", "Slack", "Share links to a channel"], ["notion", "Notion", "Sync to a database"], ["calendar", "Calendar", "Turn To-Dos into events"]];
  return <div className="ln-rise">
    <div style={{ width: 52, height: 52, borderRadius: 16, background: t.soft, display: "grid", placeItems: "center", marginBottom: 14 }}><Link2 size={24} color={t.ai} strokeWidth={2.1} /></div>
    <Section>Integrations</Section>
    {apps.map(([k, name, desc]) => <Row key={k} title={name} desc={desc}>
      <button onClick={() => onToggle(k)} style={{ border: `1.5px solid ${state[k] ? t.ai : t.line}`, background: state[k] ? t.soft : t.card, color: state[k] ? t.ai : t.ink, borderRadius: 99, padding: "7px 14px", fontSize: 13, fontWeight: 600, cursor: "pointer" }}>{state[k] ? "Connected" : "Connect"}</button></Row>)}
  </div>;
}

function HelpView() {
  const t = useT(); const [open, setOpen] = useState(-1);
  const faq = [
    ["How does AI search work?", "Type a query in the search bar — it hits the /api/search endpoint on the backend which returns relevant saved links matched by keyword scoring."],
    ["How do I save a link?", "Tap the + button, paste a URL, and hit Save. The backend scrapes metadata and AI-enriches it in the background."],
    ["Where do deleted links go?", "To Trash. You can restore them anytime, or empty the trash to remove them permanently."],
    ["Why is a link showing 'AI enriching…'?", "The backend queues AI processing asynchronously. The link is saved immediately but enrichment may take a few seconds."],
    ["How do I start the backend?", "Run python dev_server.py from the backend/ folder. It starts on http://localhost:8000."],
  ];
  return <div className="ln-rise">
    <div style={{ width: 52, height: 52, borderRadius: 16, background: t.soft, display: "grid", placeItems: "center", marginBottom: 14 }}><HelpCircle size={24} color={t.ai} strokeWidth={2.1} /></div>
    <Section>FAQ</Section>
    {faq.map(([q, a], i) => <div key={i} style={{ borderTop: `1px solid ${t.line}` }}>
      <button onClick={() => setOpen(open === i ? -1 : i)} style={{ width: "100%", display: "flex", justifyContent: "space-between", alignItems: "center", gap: 10, padding: "14px 0", background: "transparent", border: "none", cursor: "pointer", color: t.ink, textAlign: "left", fontSize: 15, fontWeight: 500 }}>{q}<ChevronRight size={17} color={t.sub} style={{ transform: open === i ? "rotate(90deg)" : "none", transition: "transform .2s" }} /></button>
      {open === i && <p style={{ margin: "0 0 14px", fontSize: 14, lineHeight: 1.5, color: t.sub }}>{a}</p>}
    </div>)}
    <Section>Contact</Section>
    <p style={{ fontSize: 14, color: t.sub, lineHeight: 1.5 }}>Reach the team at <span style={{ color: t.ai, fontWeight: 600 }}>hello@haystek.co</span>.</p>
  </div>;
}

function AboutView({ onToast, backendOnline }) {
  const t = useT();
  return <div className="ln-rise" style={{ textAlign: "center", paddingTop: 10 }}>
    <div style={{ width: 70, height: 70, borderRadius: 22, background: "#DDD0F5", display: "grid", placeItems: "center", margin: "0 auto 14px" }}><Globe size={32} color="#43306E" strokeWidth={2} /></div>
    <h2 className="disp" style={{ fontSize: 26, fontWeight: 600, margin: 0 }}>Knowledge Vault</h2>
    <div style={{ color: t.sub, fontSize: 14, marginTop: 4 }}>Version 1.0 · build 001</div>
    <div style={{ marginTop: 10, display: "inline-flex", alignItems: "center", gap: 6, background: backendOnline ? "#16A37B18" : "#F2664E18", borderRadius: 99, padding: "6px 14px", fontSize: 13, color: backendOnline ? "#16A37B" : "#d05a48", fontWeight: 600 }}>
      <div style={{ width: 7, height: 7, borderRadius: 99, background: backendOnline ? "#16A37B" : "#F2664E" }} />
      {backendOnline ? "Backend connected" : "Backend offline"}
    </div>
    <p style={{ color: t.sub, fontSize: 14, lineHeight: 1.5, margin: "16px 0 22px" }}>An AI-powered link vault. Save any URL, get AI summaries, search your entire knowledge base.</p>
    <div style={{ textAlign: "left" }}>
      {[["View API docs", "Opening http://localhost:8000/docs…"], ["Terms of service", "Opening terms…"], ["Privacy policy", "Opening privacy policy…"]].map(([l, msg]) => <LinkRow key={l} label={l} onClick={() => onToast(msg)} />)}
    </div>
  </div>;
}

// ---- ACCOUNT ---------------------------------------------------------------
function AccountView({ user, onSave, onUpgrade }) {
  const t = useT();
  const [name, setName] = useState(user.name); const [email, setEmail] = useState(user.email);
  const [bio, setBio] = useState(user.bio); const [avatar, setAvatar] = useState(user.avatar);
  const Field = ({ icon: Icon, label, value, set, type, area }) => <div style={{ marginBottom: 14 }}>
    <div style={{ fontSize: 13, color: t.sub, marginBottom: 6 }}>{label}</div>
    <div style={{ display: "flex", alignItems: area ? "flex-start" : "center", gap: 10, background: t.card, border: `1.5px solid ${t.line}`, borderRadius: 14, padding: "12px 14px" }}>
      <Icon size={17} color={t.sub} style={{ marginTop: area ? 2 : 0 }} />
      {area ? <textarea value={value} onChange={(e) => set(e.target.value)} rows={2} style={{ flex: 1, border: "none", outline: "none", fontSize: 15, background: "transparent", color: t.ink, resize: "none" }} />
        : <input value={value} type={type || "text"} onChange={(e) => set(e.target.value)} style={{ flex: 1, border: "none", outline: "none", fontSize: 15, background: "transparent", color: t.ink }} />}</div></div>;
  return <div className="ln-rise">
    <div style={{ textAlign: "center", marginBottom: 16 }}>
      <div style={{ width: 72, height: 72, borderRadius: 24, background: avatar, display: "grid", placeItems: "center", margin: "0 auto 12px", fontSize: 30, fontWeight: 600, color: "#5a3a1a" }}>{name[0]?.toUpperCase() || "?"}</div>
      <div style={{ display: "flex", gap: 8, justifyContent: "center" }}>{AVATARS.map((a) => <button key={a} onClick={() => setAvatar(a)} style={{ width: 26, height: 26, borderRadius: 99, background: a, border: avatar === a ? `2.5px solid ${t.ink}` : "2.5px solid transparent", cursor: "pointer" }} />)}</div></div>
    <Field icon={User} label="Name" value={name} set={setName} />
    <Field icon={Mail} label="Email" value={email} set={setEmail} type="email" />
    <Field icon={FileText} label="Bio" value={bio} set={setBio} area />
    <button onClick={() => onSave({ ...user, name: name || "You", email, bio, avatar })} style={{ width: "100%", border: "none", borderRadius: 16, padding: "14px", fontSize: 15, fontWeight: 600, background: t.ink, color: t.paper, cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", gap: 8 }}><Check size={17} strokeWidth={2.5} /> Save changes</button>
    <button onClick={onUpgrade} style={{ width: "100%", marginTop: 10, border: `1.5px solid ${t.line}`, borderRadius: 16, padding: "13px", fontSize: 14, fontWeight: 600, background: t.card, color: t.ai, cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", gap: 8 }}><Crown size={16} /> {user.plan === "Pro" ? "Manage plan" : "Upgrade to Pro"}</button>
  </div>;
}

// ---- UPGRADE ---------------------------------------------------------------
function UpgradeView({ plan, onPick }) {
  const t = useT();
  const plans = [
    { id: "Free", price: "$0", tag: "The basics", feats: ["6 categories", "AI search (10/day)", "Local link vault"] },
    { id: "Pro", price: "$6/mo", tag: "Everything unlocked", feats: ["Unlimited AI search", "Full content extraction", "Vector semantic search", "Connected apps", "Priority support"] }
  ];
  return <div className="ln-rise">
    <div style={{ textAlign: "center", marginBottom: 18 }}>
      <div style={{ width: 56, height: 56, borderRadius: 18, background: "#FFF1C2", display: "grid", placeItems: "center", margin: "0 auto 10px" }}><Crown size={26} color="#C99700" fill="#FFD75A" /></div>
      <h2 className="disp" style={{ fontSize: 24, fontWeight: 600, margin: 0 }}>Go Pro</h2>
      <p style={{ color: t.sub, fontSize: 14, margin: "4px 0 0" }}>Unlock the full Knowledge Vault.</p></div>
    {plans.map((p) => { const cur = plan === p.id; const pro = p.id === "Pro";
      return <div key={p.id} style={{ border: `2px solid ${pro ? t.ai : t.line}`, background: pro ? t.soft : t.card, borderRadius: 20, padding: 18, marginBottom: 14, position: "relative" }}>
        {pro && <span style={{ position: "absolute", top: -10, right: 16, background: t.ai, color: "#fff", fontSize: 11, fontWeight: 700, padding: "3px 10px", borderRadius: 99 }}>BEST VALUE</span>}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}><div className="disp" style={{ fontSize: 20, fontWeight: 600 }}>{p.id}</div><div style={{ fontWeight: 600, fontSize: 16 }}>{p.price}</div></div>
        <div style={{ fontSize: 12.5, color: t.sub, marginBottom: 12 }}>{p.tag}</div>
        {p.feats.map((f, i) => <div key={i} style={{ display: "flex", gap: 8, alignItems: "center", fontSize: 13.5, padding: "4px 0" }}><Check size={15} strokeWidth={2.6} color={pro ? t.ai : t.sub} /> {f}</div>)}
        <button disabled={cur} onClick={() => onPick(p.id)} style={{ width: "100%", marginTop: 14, border: "none", borderRadius: 14, padding: "12px", fontSize: 14, fontWeight: 600, cursor: cur ? "default" : "pointer", background: cur ? t.hair : pro ? t.ai : t.ink, color: cur ? t.sub : "#fff" }}>{cur ? "Current plan" : pro ? "Upgrade to Pro" : "Switch to Free"}</button></div>; })}
  </div>;
}

// ---- LOGGED OUT ------------------------------------------------------------
function LoggedOut({ user, onLogin }) {
  const t = useT();
  return <div style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: 30, textAlign: "center" }}>
    <div style={{ width: 70, height: 70, borderRadius: 22, background: "#DDD0F5", display: "grid", placeItems: "center", marginBottom: 18 }}><Globe size={32} color="#43306E" strokeWidth={2} /></div>
    <h1 className="disp" style={{ fontSize: 30, fontWeight: 600, margin: 0 }}>Knowledge Vault</h1>
    <p style={{ color: t.sub, fontSize: 15, margin: "8px 0 28px" }}>You're logged out. See you soon, {user.name}.</p>
    <button onClick={onLogin} style={{ width: "100%", border: "none", borderRadius: 16, padding: "15px", fontSize: 15.5, fontWeight: 600, background: t.ink, color: t.paper, cursor: "pointer" }}>Log back in</button></div>;
}

// ---- CONFIRM ---------------------------------------------------------------
function ConfirmModal({ title, text, yes, danger, onYes, onClose }) {
  const t = useT();
  return <><div onClick={onClose} style={{ position: "absolute", inset: 0, background: "rgba(20,15,10,.5)", zIndex: 96 }} />
    <div className="ln-rise" style={{ position: "absolute", left: 28, right: 28, top: "40%", zIndex: 97, background: t.card, borderRadius: 22, padding: 22, boxShadow: "0 20px 60px rgba(0,0,0,.4)" }}>
      <div className="disp" style={{ fontSize: 19, fontWeight: 600, marginBottom: 6 }}>{title}</div>
      <p style={{ margin: "0 0 18px", fontSize: 14, color: t.sub, lineHeight: 1.45 }}>{text}</p>
      <div style={{ display: "flex", gap: 10 }}>
        <button onClick={onClose} style={{ flex: 1, border: `1.5px solid ${t.line}`, background: t.card, color: t.ink, borderRadius: 13, padding: "12px", fontSize: 14, fontWeight: 600, cursor: "pointer" }}>Cancel</button>
        <button onClick={() => { onYes(); onClose(); }} style={{ flex: 1, border: "none", background: danger ? "#d05a48" : t.ai, color: "#fff", borderRadius: 13, padding: "12px", fontSize: 14, fontWeight: 600, cursor: "pointer" }}>{yes}</button>
      </div></div></>;
}

// ---- COMPOSE (now: Save Link) ----------------------------------------------
function ComposeSheet({ open, onClose, onSave, defaultCat, spellcheck }) {
  const t = useT();
  const [url, setUrl] = useState(""); const [notes, setNotes] = useState(""); const [cat, setCat] = useState(defaultCat);
  const [saving, setSaving] = useState(false);
  useEffect(() => { if (open) { setUrl(""); setNotes(""); setCat(defaultCat); } }, [open, defaultCat]);

  async function paste() { try { const x = await navigator.clipboard.readText(); setUrl(x.trim()); } catch {} }

  const isValidUrl = (s) => { try { new URL(s); return true; } catch { return false; } };
  const canSave = isValidUrl(url.trim()) && !saving;

  async function handleSave() {
    if (!canSave) return;
    setSaving(true);
    try { await onSave({ url: url.trim(), notes: notes.trim() || undefined, cat }); }
    finally { setSaving(false); }
  }

  return <><div onClick={onClose} style={{ position: "absolute", inset: 0, background: "rgba(20,15,10,.4)", zIndex: 70, opacity: open ? 1 : 0, pointerEvents: open ? "auto" : "none", transition: "opacity .3s" }} />
    <div style={{ position: "absolute", left: 0, right: 0, bottom: 0, zIndex: 75, background: t.paper, borderRadius: "28px 28px 0 0", padding: "10px 22px 24px", transition: "transform .34s", transform: open ? "none" : "translateY(100%)", boxShadow: "0 -10px 40px rgba(0,0,0,.25)", maxHeight: "82%", overflowY: "auto" }} className="ln-scroll">
      <div style={{ width: 44, height: 5, background: t.line, borderRadius: 99, margin: "0 auto 14px" }} />
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14 }}>
        <h3 className="disp" style={{ fontSize: 22, fontWeight: 600, margin: 0 }}>Save a Link</h3>
        <button onClick={onClose} style={iconBtn(t)}><X size={18} strokeWidth={2.2} /></button></div>

      {/* URL input */}
      <div style={{ fontSize: 13, color: t.sub, marginBottom: 6 }}>URL *</div>
      <div style={{ position: "relative", marginBottom: 10 }}>
        <input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://…" style={{ width: "100%", border: `1.5px solid ${isValidUrl(url.trim()) ? t.ai : t.line}`, borderRadius: 14, padding: "12px 48px 12px 14px", fontSize: 15, fontWeight: 500, outline: "none", background: t.card, color: t.ink }} />
        <button onClick={paste} style={{ position: "absolute", right: 10, top: "50%", transform: "translateY(-50%)", display: "flex", alignItems: "center", gap: 4, background: t.soft, color: t.ai, border: "none", borderRadius: 10, padding: "6px 9px", fontSize: 12, fontWeight: 600, cursor: "pointer" }}><Clipboard size={13} strokeWidth={2.4} /></button>
      </div>

      {/* Notes */}
      <div style={{ fontSize: 13, color: t.sub, marginBottom: 6 }}>Notes (optional)</div>
      <textarea value={notes} spellCheck={spellcheck} onChange={(e) => setNotes(e.target.value)} placeholder="Add context, why you saved this…" style={{ width: "100%", minHeight: 80, border: `1.5px solid ${t.line}`, borderRadius: 14, padding: "12px 14px", fontSize: 14.5, lineHeight: 1.5, outline: "none", resize: "none", background: t.card, color: t.ink, marginBottom: 12 }} />

      {/* Category */}
      <div style={{ fontSize: 13, color: t.sub, marginBottom: 8 }}>Category</div>
      <div style={{ display: "flex", gap: 8, overflowX: "auto", paddingBottom: 14 }} className="ln-scroll">
        {CAT_IDS.map((id) => { const on = cat === id; return <button key={id} onClick={() => setCat(id)} style={{ whiteSpace: "nowrap", cursor: "pointer", border: `1.5px solid ${on ? CATS[id].fg : t.line}`, background: on ? CATS[id].bg : t.card, color: on ? CATS[id].fg : t.ink, borderRadius: 999, padding: "8px 14px", fontSize: 13.5, fontWeight: 600 }}>{CATS[id].name}</button>; })}
      </div>

      <button disabled={!canSave} onClick={handleSave} style={{ width: "100%", border: "none", borderRadius: 16, padding: "15px", fontSize: 15.5, fontWeight: 600, cursor: canSave ? "pointer" : "not-allowed", color: "#fff", background: canSave ? t.ink : (t.dark ? "#3a322a" : "#cfc7bb"), display: "flex", alignItems: "center", justifyContent: "center", gap: 8 }}>
        {saving ? <><Loader size={18} strokeWidth={2.4} className="spinning" /> Saving…</> : <><Check size={18} strokeWidth={2.6} /> Save link</>}
      </button>
    </div></>;
}

// ---- helpers ---------------------------------------------------------------
const iconBtn = (t) => ({ width: 40, height: 40, borderRadius: 14, border: `1px solid ${t.line}`, background: t.card, display: "grid", placeItems: "center", cursor: "pointer", color: t.ink });
const filterPill = (t, on) => ({ border: `1.5px solid ${on ? t.ink : t.line}`, background: on ? t.ink : t.card, color: on ? t.paper : t.ink, borderRadius: 999, padding: "8px 16px", fontSize: 14, fontWeight: 500, whiteSpace: "nowrap", cursor: "pointer" });
const menuRow = (t) => ({ width: "100%", display: "flex", alignItems: "center", justifyContent: "space-between", background: "transparent", border: "none", borderTop: `1px solid ${t.line}`, padding: "14px 2px", fontSize: 15, color: t.ink, cursor: "pointer", fontWeight: 500 });

function Overlay({ open, onClose, side, children }) {
  const t = useT();
  return <><div onClick={onClose} style={{ position: "absolute", inset: 0, background: "rgba(20,15,10,.4)", zIndex: 50, opacity: open ? 1 : 0, pointerEvents: open ? "auto" : "none", transition: "opacity .3s" }} />
    <div className="ln-scroll" style={{ position: "absolute", top: 0, bottom: 0, [side]: 0, width: "82%", background: t.paper, zIndex: 60, padding: "56px 22px 30px", transition: "transform .32s", transform: open ? "none" : `translateX(${side === "left" ? "-100%" : "100%"})`, boxShadow: "0 0 60px rgba(0,0,0,.3)", borderRadius: side === "left" ? "0 28px 28px 0" : "28px 0 0 28px", overflowY: "auto", color: t.ink }}>
      <button onClick={onClose} style={{ ...iconBtn(t), position: "absolute", top: 16, [side === "left" ? "right" : "left"]: 18 }}><X size={18} strokeWidth={2.2} /></button>
      {children}</div></>;
}
