import { writable, get } from "svelte/store";
import type { OpenTab } from "$lib/types";

// Editor tabs (desktop). There is still a single editor: a tab is just a
// remembered note path, and switching tabs loads that note into the editor.
// An empty tab (path === null) shows the empty editor until a note is picked,
// which then opens in that tab.

export interface Tab {
  id: number;
  path: string | null;
  title: string;
}

export interface TabsState {
  tabs: Tab[];
  active: number; // index into tabs, -1 when there are none
}

let nextId = 1;

function normalize(path: string): string {
  return path.replace(/\\/g, "/");
}

export function samePath(a: string | null | undefined, b: string | null | undefined): boolean {
  return a != null && b != null && normalize(a) === normalize(b);
}

export function titleFromPath(path: string | null): string {
  if (!path) return "New tab";
  const name = normalize(path).split("/").pop() ?? path;
  return name.replace(/\.md$/i, "");
}

function makeTab(path: string | null, title?: string | null): Tab {
  return { id: nextId++, path, title: title || titleFromPath(path) };
}

function createTabs() {
  const store = writable<TabsState>({ tabs: [], active: -1 });
  const { subscribe, update, set } = store;
  // Recently closed notes, newest last, for "Reopen closed tab" (not saved).
  let closed: string[] = [];

  return {
    subscribe,

    clear() {
      closed = [];
      set({ tabs: [], active: -1 });
    },

    /** Remember notes the user closed so Ctrl+Shift+T can bring them back. */
    rememberClosed(paths: (string | null)[]) {
      for (const path of paths) {
        if (!path) continue;
        closed = closed.filter((p) => !samePath(p, path));
        closed.push(path);
      }
      if (closed.length > 30) closed = closed.slice(-30);
    },

    /** Most recently closed note that is not already open, or null. */
    takeClosed(): string | null {
      const open = get(store).tabs;
      while (closed.length) {
        const path = closed.pop()!;
        if (!open.some((t) => samePath(t.path, path))) return path;
      }
      return null;
    },

    /** Load tabs saved in the vault state. */
    restore(saved: OpenTab[] | undefined, active: number | undefined) {
      const tabs = (saved ?? [])
        .filter((t) => t && typeof t.path === "string" && t.path)
        .map((t) => makeTab(t.path, t.title));
      const index = tabs.length ? Math.min(Math.max(active ?? 0, 0), tabs.length - 1) : -1;
      set({ tabs, active: index });
    },

    activeTab(): Tab | null {
      const s = get(store);
      return s.tabs[s.active] ?? null;
    },

    find(path: string): Tab | null {
      return get(store).tabs.find((t) => samePath(t.path, path)) ?? null;
    },

    byId(id: number): Tab | null {
      return get(store).tabs.find((t) => t.id === id) ?? null;
    },

    /**
     * Keep tabs in step with the note shown in the editor. Any navigation
     * (note list, search, wiki link, history...) lands here: a note that is
     * already open in a tab activates that tab, otherwise it replaces the
     * note in the current tab, like Obsidian.
     */
    noteShown(path: string | null, title: string | null) {
      if (!path) return;
      update((s) => {
        const current = s.tabs[s.active];
        if (current && samePath(current.path, path)) {
          if (!title || current.title === title) return s;
          const tabs = s.tabs.slice();
          tabs[s.active] = { ...current, title };
          return { ...s, tabs };
        }
        const existing = s.tabs.findIndex((t) => samePath(t.path, path));
        if (existing >= 0) {
          if (!title || s.tabs[existing].title === title) return { ...s, active: existing };
          const tabs = s.tabs.slice();
          tabs[existing] = { ...tabs[existing], title };
          return { tabs, active: existing };
        }
        if (!current) {
          return { tabs: [...s.tabs, makeTab(path, title)], active: s.tabs.length };
        }
        const tabs = s.tabs.slice();
        tabs[s.active] = { ...current, path, title: title || titleFromPath(path) };
        return { ...s, tabs };
      });
    },

    /** Insert a tab right after the active one and make it active. */
    add(path: string | null, title?: string | null): Tab {
      const tab = makeTab(path, title);
      update((s) => {
        const at = s.active < 0 ? s.tabs.length : s.active + 1;
        const tabs = s.tabs.slice();
        tabs.splice(at, 0, tab);
        return { tabs, active: at };
      });
      return tab;
    },

    activate(id: number) {
      update((s) => {
        const index = s.tabs.findIndex((t) => t.id === id);
        return index < 0 || index === s.active ? s : { ...s, active: index };
      });
    },

    /** Turn a tab into an empty "New tab". */
    empty(id: number) {
      update((s) => ({
        ...s,
        tabs: s.tabs.map((t) => (t.id === id ? { ...t, path: null, title: titleFromPath(null) } : t)),
      }));
    },

    /**
     * Remove a tab. When it was the active one, the tab to its right (or else
     * its left) becomes active; the caller loads that tab's note.
     */
    remove(id: number) {
      update((s) => {
        const index = s.tabs.findIndex((t) => t.id === id);
        if (index < 0) return s;
        const tabs = s.tabs.filter((t) => t.id !== id);
        let active = s.active;
        if (index < s.active) active--;
        else if (index === s.active) active = Math.min(index, tabs.length - 1);
        return { tabs, active: tabs.length ? active : -1 };
      });
    },

    /** Keep only the given tabs (used by "Close others" / "Close to the right"). */
    keep(ids: number[], activeId: number) {
      update((s) => {
        const tabs = s.tabs.filter((t) => ids.includes(t.id));
        return { tabs, active: tabs.findIndex((t) => t.id === activeId) };
      });
    },

    /** Drag-to-reorder. */
    move(id: number, toIndex: number) {
      update((s) => {
        const from = s.tabs.findIndex((t) => t.id === id);
        if (from < 0) return s;
        const activeId = s.tabs[s.active]?.id;
        const tabs = s.tabs.slice();
        const [tab] = tabs.splice(from, 1);
        const to = Math.max(0, Math.min(toIndex > from ? toIndex - 1 : toIndex, tabs.length));
        tabs.splice(to, 0, tab);
        return { tabs, active: tabs.findIndex((t) => t.id === activeId) };
      });
    },

    /** A note or folder was renamed/moved: follow it in every tab. */
    remap(oldPrefix: string, newPrefix: string, newTitle?: string | null) {
      const oldRoot = normalize(oldPrefix).replace(/\/+$/, "");
      const newRoot = newPrefix.replace(/[\\/]+$/, "");
      const insensitive = /^[A-Za-z]:\//.test(oldRoot) || oldRoot.startsWith("//");
      const matchRoot = insensitive ? oldRoot.toLowerCase() : oldRoot;
      update((s) => {
        let changed = false;
        const tabs = s.tabs.map((t) => {
          if (!t.path) return t;
          const candidate = insensitive ? normalize(t.path).toLowerCase() : normalize(t.path);
          if (candidate !== matchRoot && !candidate.startsWith(`${matchRoot}/`)) return t;
          changed = true;
          const path = newRoot + t.path.slice(oldRoot.length);
          const title = candidate === matchRoot ? newTitle || titleFromPath(path) : t.title;
          return { ...t, path, title };
        });
        return changed ? { ...s, tabs } : s;
      });
    },

    /** Shape stored in the vault state (empty tabs are not remembered). */
    serialize(): { open_tabs: OpenTab[]; active_tab: number } {
      const s = get(store);
      const activeId = s.tabs[s.active]?.id;
      const kept = s.tabs.filter((t) => t.path);
      const active = kept.findIndex((t) => t.id === activeId);
      return {
        open_tabs: kept.map((t) => ({ path: t.path!, title: t.title })),
        active_tab: active < 0 ? Math.max(0, kept.length - 1) : active,
      };
    },
  };
}

export const tabs = createTabs();
