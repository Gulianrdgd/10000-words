<script lang="ts">
	import { page } from '$app/stores';

	// hand-drawn 1.75px-stroke icons, one per tab
	const tabs = [
		{ href: '/', label: 'Review', icon: 'M4 6.5A2.5 2.5 0 0 1 6.5 4H13l7 7v6.5a2.5 2.5 0 0 1-2.5 2.5h-11A2.5 2.5 0 0 1 4 17.5v-11ZM13 4v4.5a2.5 2.5 0 0 0 2.5 2.5H20' },
		{ href: '/goals', label: 'Goals', icon: 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Zm0-4.5a4.5 4.5 0 1 0 0-9 4.5 4.5 0 0 0 0 9Zm0-3.5a1 1 0 1 0 0-2 1 1 0 0 0 0 2Z' },
		{ href: '/progress', label: 'Progress', icon: 'M4 20h16M7 16v-5m5 5V6m5 10v-8' },
		{ href: '/settings', label: 'Settings', icon: 'M4 7h9m4 0h3M4 17h3m4 0h9M15 9.5a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5ZM9 19.5a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5Z' }
	];

	/** Published as --nav-h so the layout and the feedback banner can sit above
	 *  the nav without either of them hardcoding its height. */
	let height = $state(0);
	$effect(() => {
		document.documentElement.style.setProperty('--nav-h', `${height}px`);
	});

	function active(href: string, path: string) {
		return href === '/' ? path === '/' : path.startsWith(href) || (href === '/progress' && path.startsWith('/words'));
	}
</script>

<nav
	bind:clientHeight={height}
	class="fixed inset-x-0 bottom-0 z-20 border-t border-ink-800/80 bg-ink-950/90 pb-[env(safe-area-inset-bottom)] backdrop-blur-md"
>
	<div class="mx-auto flex max-w-md px-2">
		{#each tabs as tab (tab.href)}
			{@const isActive = active(tab.href, $page.url.pathname)}
			<a
				href={tab.href}
				aria-current={isActive ? 'page' : undefined}
				class="group flex flex-1 flex-col items-center gap-1 py-2.5 text-[0.6875rem] font-medium transition-colors duration-200 {isActive
					? 'text-paper'
					: 'text-ink-500 hover:text-ink-300'}"
			>
				<svg
					viewBox="0 0 24 24"
					fill="none"
					stroke="currentColor"
					stroke-width="1.75"
					stroke-linecap="round"
					stroke-linejoin="round"
					class="h-[1.375rem] w-[1.375rem] transition-transform duration-200 group-active:scale-90"
					aria-hidden="true"
				>
					<path d={tab.icon} />
				</svg>
				{tab.label}
			</a>
		{/each}
	</div>
</nav>
