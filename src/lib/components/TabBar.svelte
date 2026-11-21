<script lang="ts">
	import { t as ui } from '$lib/i18n';
	import { tick } from 'svelte';
	import { tabs, type Tab } from '$lib/stores/tabs';

	let {
		onSelect,
		onClose,
		onNew,
		onCloseMany,
	}: {
		onSelect: (id: number) => void;
		onClose: (id: number) => void;
		onNew: () => void;
		onCloseMany: (keepIds: number[], activeId: number) => void;
	} = $props();

	let strip = $state<HTMLDivElement>();
	let menu = $state<{ x: number; y: number; tab: Tab } | null>(null);
	let dragId = $state<number | null>(null);
	let dropIndex = $state<number | null>(null);

	// Keep the active tab visible when a different tab becomes active. Only the
	// active tab's id is tracked, so reordering, renames or closing other tabs
	// never yank the strip away from where the user scrolled it.
	const activeId = $derived($tabs.tabs[$tabs.active]?.id ?? null);
	$effect(() => {
		const id = activeId;
		if (id === null) return;
		void tick().then(() => {
			const el = strip?.querySelector<HTMLElement>(`[data-tab-id="${id}"]`);
			el?.scrollIntoView({ block: 'nearest', inline: 'nearest' });
		});
	});

	function openMenu(e: MouseEvent, tab: Tab) {
		e.preventDefault();
		const x = Math.min(e.clientX, window.innerWidth - 220);
		const y = Math.min(e.clientY, window.innerHeight - 120);
		menu = { x, y, tab };
	}

	function closeOthers(tab: Tab) {
		menu = null;
		onCloseMany([tab.id], tab.id);
	}

	function closeRight(tab: Tab) {
		menu = null;
		const index = $tabs.tabs.findIndex((t) => t.id === tab.id);
		const keep = $tabs.tabs.slice(0, index + 1).map((t) => t.id);
		const activeId = $tabs.tabs[$tabs.active]?.id;
		onCloseMany(keep, activeId != null && keep.includes(activeId) ? activeId : tab.id);
	}

	function dropTarget(e: DragEvent, index: number): number {
		const rect = (e.currentTarget as HTMLElement).getBoundingClientRect();
		return e.clientX < rect.left + rect.width / 2 ? index : index + 1;
	}

	// WebKitGTK sometimes skips the final 'drop' event. The marker shown while
	// dragging is the user's intent, so dragend completes the move when the
	// pointer was still over a tab; leaving the tab bar clears the marker.
	function finishDrag() {
		if (dragId !== null && dropIndex !== null) tabs.move(dragId, dropIndex);
		dragId = null;
		dropIndex = null;
	}

	function handleStripDragLeave(e: DragEvent) {
		const next = e.relatedTarget as Node | null;
		if (!next || !strip?.contains(next)) dropIndex = null;
	}

	function handleWheel(e: WheelEvent) {
		if (!strip || Math.abs(e.deltaY) <= Math.abs(e.deltaX)) return;
		strip.scrollLeft += e.deltaY;
		e.preventDefault();
	}
</script>

<svelte:window
	onmousedown={(e) => { if (menu && !(e.target as HTMLElement).closest?.('.tab-menu')) menu = null; }}
	onkeydown={(e) => { if (menu && e.key === 'Escape') { e.stopPropagation(); menu = null; } }}
/>

<div class="tab-bar" role="tablist" aria-label="Tabs" tabindex="-1" ondblclick={(e) => { if (e.target === e.currentTarget) onNew(); }}>
	<div class="tab-strip" bind:this={strip} onwheel={handleWheel} ondragleave={handleStripDragLeave} ondblclick={(e) => { if (e.target === e.currentTarget) onNew(); }} role="presentation">
		{#each $tabs.tabs as tab, index (tab.id)}
			<div
				class="tab"
				data-tab-id={tab.id}
				class:active={index === $tabs.active}
				class:empty={!tab.path}
				class:dragging={dragId === tab.id}
				class:drop-before={dropIndex === index && dragId !== null}
				class:drop-after={dropIndex === index + 1 && index === $tabs.tabs.length - 1 && dragId !== null}
				role="tab"
				tabindex="0"
				aria-selected={index === $tabs.active}
				title={tab.path ?? tab.title}
				draggable="true"
				onclick={() => onSelect(tab.id)}
				onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onSelect(tab.id); } }}
				onmousedown={(e) => { if (e.button === 1) e.preventDefault(); }}
				onauxclick={(e) => { if (e.button === 1) { e.preventDefault(); onClose(tab.id); } }}
				oncontextmenu={(e) => openMenu(e, tab)}
				ondragstart={(e) => {
					dragId = tab.id;
					e.dataTransfer!.setData('application/x-helix-tab', String(tab.id));
					e.dataTransfer!.effectAllowed = 'move';
				}}
				ondragover={(e) => {
					if (dragId === null) return;
					e.preventDefault();
					e.dataTransfer!.dropEffect = 'move';
					dropIndex = dropTarget(e, index);
				}}
				ondrop={(e) => {
					if (dragId === null) return;
					e.preventDefault();
					dropIndex = dropTarget(e, index);
					finishDrag();
				}}
				ondragend={finishDrag}
			>
				<span class="tab-title">{tab.path ? tab.title : $ui('ui.new_tab')}</span>
				<button
					class="tab-close"
					tabindex="-1"
					title={$ui('ui.close_tab')}
					aria-label={$ui('ui.close_tab')}
					onclick={(e) => { e.stopPropagation(); onClose(tab.id); }}
				>
					<svg width="10" height="10" viewBox="0 0 10 10"><line x1="2" y1="2" x2="8" y2="8" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/><line x1="8" y1="2" x2="2" y2="8" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/></svg>
				</button>
			</div>
		{/each}
	</div>
	<!-- Outside the scrolling strip so it stays visible with many tabs. -->
	<button class="tab-new" title={$ui('ui.new_tab')} aria-label={$ui('ui.new_tab')} onclick={onNew}>
		<svg width="12" height="12" viewBox="0 0 12 12"><line x1="6" y1="1.5" x2="6" y2="10.5" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/><line x1="1.5" y1="6" x2="10.5" y2="6" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/></svg>
	</button>
</div>

{#if menu}
	{@const tab = menu.tab}
	<div class="tab-menu" style="left: {menu.x}px; top: {menu.y}px" role="menu">
		<button role="menuitem" onclick={() => { menu = null; onClose(tab.id); }}>{$ui('ui.close_tab')}</button>
		<button role="menuitem" disabled={$tabs.tabs.length < 2} onclick={() => closeOthers(tab)}>{$ui('ui.close_other_tabs')}</button>
		<button role="menuitem" disabled={$tabs.tabs[$tabs.tabs.length - 1]?.id === tab.id} onclick={() => closeRight(tab)}>{$ui('ui.close_tabs_to_the_right')}</button>
	</div>
{/if}

<style>
	.tab-bar {
		flex-shrink: 0;
		display: flex;
		align-items: flex-end;
		height: 36px;
		padding: 0 6px;
		background: var(--bg-secondary);
		border-bottom: 1px solid var(--border-color);
		user-select: none;
		-webkit-user-select: none;
	}

	.tab-strip {
		flex: 0 1 auto;
		min-width: 0;
		height: 100%;
		display: flex;
		align-items: flex-end;
		gap: 2px;
		overflow-x: auto;
		overflow-y: hidden;
		scrollbar-width: none;
	}
	.tab-strip::-webkit-scrollbar { display: none; }

	.tab {
		position: relative;
		flex: 0 1 200px;
		min-width: 90px;
		max-width: 220px;
		height: 30px;
		display: flex;
		align-items: center;
		gap: 4px;
		padding: 0 6px 0 12px;
		border: 1px solid transparent;
		border-bottom: none;
		border-radius: 7px 7px 0 0;
		color: var(--text-secondary);
		font-size: 12.5px;
		cursor: pointer;
		outline: none;
	}
	.tab:hover { background: var(--bg-hover); }
	.tab:focus-visible { box-shadow: inset 0 0 0 1px var(--accent); }
	.tab.active {
		background: var(--bg-editor);
		border-color: var(--border-color);
		color: var(--text-primary);
		margin-bottom: -1px;
		height: 31px;
	}
	/* Separators between inactive tabs, like Obsidian. */
	.tab:not(.active) + .tab:not(.active)::before {
		content: '';
		position: absolute;
		left: -2px;
		top: 8px;
		bottom: 8px;
		width: 1px;
		background: var(--border-color);
	}
	.tab.empty .tab-title { font-style: italic; color: var(--text-tertiary); }
	.tab.dragging { opacity: 0.5; }
	.tab.drop-before { box-shadow: inset 2px 0 0 var(--accent); }
	.tab.drop-after { box-shadow: inset -2px 0 0 var(--accent); }

	.tab-title {
		flex: 1;
		min-width: 0;
		overflow: hidden;
		white-space: nowrap;
		text-overflow: ellipsis;
	}

	.tab-close,
	.tab-new {
		flex-shrink: 0;
		display: flex;
		align-items: center;
		justify-content: center;
		border: none;
		background: transparent;
		color: var(--text-tertiary);
		border-radius: 4px;
		cursor: pointer;
		padding: 0;
	}
	.tab-close { width: 18px; height: 18px; opacity: 0; }
	.tab:hover .tab-close,
	.tab.active .tab-close { opacity: 1; }
	.tab-close:hover { background: var(--bg-active); color: var(--text-primary); }

	.tab-new {
		width: 26px;
		height: 26px;
		margin: 0 0 3px 4px;
	}
	.tab-new:hover { background: var(--bg-hover); color: var(--text-primary); }

	.tab-menu {
		position: fixed;
		z-index: 1000;
		min-width: 190px;
		padding: 4px;
		background: var(--bg-primary);
		border: 1px solid var(--border-color);
		border-radius: 8px;
		box-shadow: var(--shadow-lg);
		display: flex;
		flex-direction: column;
	}
	.tab-menu button {
		text-align: left;
		border: none;
		background: transparent;
		color: var(--text-primary);
		font-size: 13px;
		padding: 6px 10px;
		border-radius: 5px;
		cursor: pointer;
	}
	.tab-menu button:hover:not(:disabled) { background: var(--bg-hover); }
	.tab-menu button:disabled { color: var(--text-tertiary); cursor: default; }
</style>
