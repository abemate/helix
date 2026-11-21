import test from 'node:test';
import assert from 'node:assert/strict';
import { get } from 'svelte/store';
import { tabs, titleFromPath } from '../src/lib/stores/tabs.ts';

const paths = () => get(tabs).tabs.map((t) => t.path);
const active = () => tabs.activeTab()?.path ?? null;

test.beforeEach(() => tabs.clear());

test('navigation replaces the current tab and reuses a tab that already shows the note', () => {
  tabs.noteShown('/v/A.md', 'A');
  assert.deepEqual(paths(), ['/v/A.md']);
  tabs.noteShown('/v/B.md', 'B');
  assert.deepEqual(paths(), ['/v/B.md'], 'replaces in place, like Obsidian');
  tabs.add('/v/C.md', 'C');
  assert.deepEqual(paths(), ['/v/B.md', '/v/C.md']);
  tabs.noteShown('/v/B.md', 'B');
  assert.equal(active(), '/v/B.md', 'switches to the existing tab instead of duplicating');
  assert.equal(get(tabs).tabs.length, 2);
});

test('an empty tab is filled by the next note, and titles follow the note', () => {
  tabs.add(null);
  assert.equal(tabs.activeTab()?.title, 'New tab');
  tabs.noteShown('/v/A.md', null);
  assert.deepEqual(paths(), ['/v/A.md']);
  assert.equal(tabs.activeTab()?.title, 'A');
  tabs.noteShown('/v/A.md', 'Renamed title');
  assert.equal(tabs.activeTab()?.title, 'Renamed title');
});

test('closing the active tab activates its right neighbour, else its left one', () => {
  for (const p of ['/v/1.md', '/v/2.md', '/v/3.md']) tabs.add(p);
  const ids = get(tabs).tabs.map((t) => t.id);
  tabs.activate(ids[1]);
  tabs.remove(ids[1]);
  assert.equal(active(), '/v/3.md');
  tabs.remove(ids[2]);
  assert.equal(active(), '/v/1.md');
  tabs.remove(ids[0]);
  assert.equal(get(tabs).active, -1);
});

test('closing a tab left of the active one keeps the same tab active', () => {
  for (const p of ['/v/1.md', '/v/2.md', '/v/3.md']) tabs.add(p);
  const ids = get(tabs).tabs.map((t) => t.id);
  tabs.remove(ids[0]);
  assert.equal(active(), '/v/3.md');
});

test('reordering keeps the active tab', () => {
  for (const p of ['/v/1.md', '/v/2.md', '/v/3.md']) tabs.add(p);
  const [a, , c] = get(tabs).tabs.map((t) => t.id);
  tabs.activate(a);
  tabs.move(a, 3);
  assert.deepEqual(paths(), ['/v/2.md', '/v/3.md', '/v/1.md']);
  assert.equal(active(), '/v/1.md');
  tabs.move(c, 0);
  assert.deepEqual(paths(), ['/v/3.md', '/v/2.md', '/v/1.md']);
  assert.equal(active(), '/v/1.md');
});

test('renaming a note or folder updates every tab under it', () => {
  tabs.add('/v/Work/A.md', 'A');
  tabs.add('/v/Work/Sub/B.md', 'B');
  tabs.add('/v/Workshop.md', 'Workshop');
  tabs.remap('/v/Work', '/v/Jobs');
  assert.deepEqual(paths(), ['/v/Jobs/A.md', '/v/Jobs/Sub/B.md', '/v/Workshop.md']);
  tabs.remap('/v/Jobs/A.md', '/v/Jobs/Alpha.md', 'Alpha');
  assert.equal(get(tabs).tabs[0].title, 'Alpha');
  assert.equal(get(tabs).tabs[1].title, 'B');
});

test('tabs survive a save/restore round trip; empty tabs are not saved', () => {
  tabs.add('/v/A.md', 'A');
  tabs.add(null);
  tabs.add('/v/B.md', 'B');
  tabs.activate(get(tabs).tabs[0].id);
  const saved = tabs.serialize();
  assert.deepEqual(saved, {
    open_tabs: [{ path: '/v/A.md', title: 'A' }, { path: '/v/B.md', title: 'B' }],
    active_tab: 0,
  });
  tabs.clear();
  tabs.restore(saved.open_tabs, saved.active_tab);
  assert.deepEqual(paths(), ['/v/A.md', '/v/B.md']);
  assert.equal(active(), '/v/A.md');
  tabs.restore([{ path: '/v/A.md', title: 'A' }], 9);
  assert.equal(active(), '/v/A.md', 'out-of-range index is clamped');
  tabs.restore(undefined, undefined);
  assert.equal(get(tabs).active, -1);
});

test('titles fall back to the file name', () => {
  assert.equal(titleFromPath('/v/Folder/My note.md'), 'My note');
  assert.equal(titleFromPath('C:\\v\\Note.md'), 'Note');
  assert.equal(titleFromPath(null), 'New tab');
});

test('closed tabs can be reopened newest first, skipping notes that are open again', () => {
  tabs.rememberClosed(['/v/A.md', null, '/v/B.md', '/v/C.md']);
  tabs.add('/v/C.md');
  assert.equal(tabs.takeClosed(), '/v/B.md', 'C is open again, so B comes back first');
  tabs.rememberClosed(['/v/A.md']);
  assert.equal(tabs.takeClosed(), '/v/A.md', 'closing again moves a note to the front');
  assert.equal(tabs.takeClosed(), null);
  tabs.rememberClosed(['/v/D.md']);
  tabs.clear();
  assert.equal(tabs.takeClosed(), null, 'switching vaults forgets the history');
});
