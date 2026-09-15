<script lang="ts">
	import { page } from '$app/stores';

	const tabs = [
		{ href: '/', label: 'Review' },
		{ href: '/goals', label: 'Goals' },
		{ href: '/progress', label: 'Progress' }
	];
</script>

<nav class="fixed bottom-0 left-0 right-0 z-20 border-t border-slate-800 bg-slate-950 pb-[env(safe-area-inset-bottom)]">
	<div class="mx-auto flex max-w-md">
		{#each tabs as tab (tab.href)}
			<a
				href={tab.href}
				class="flex-1 border-t-2 py-3 text-center text-sm font-medium transition-colors"
				class:border-brand-400={$page.url.pathname === tab.href}
				class:text-slate-100={$page.url.pathname === tab.href}
				class:border-transparent={$page.url.pathname !== tab.href}
				class:text-slate-500={$page.url.pathname !== tab.href}
			>
				{tab.label}
			</a>
		{/each}
	</div>
</nav>
