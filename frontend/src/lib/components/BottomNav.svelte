<script lang="ts">
	import { page } from '$app/stores';

	const tabs = [
		{ href: '/', label: 'Review', icon: '📖' },
		{ href: '/goals', label: 'Goals', icon: '🎯' },
		{ href: '/progress', label: 'Progress', icon: '📈' }
	];
</script>

<nav
	class="fixed bottom-0 left-0 right-0 z-20 border-t border-slate-800 bg-slate-950/95 backdrop-blur pb-[env(safe-area-inset-bottom)]"
>
	<div class="mx-auto flex max-w-md">
		{#each tabs as tab (tab.href)}
			<a
				href={tab.href}
				class="flex flex-1 flex-col items-center gap-0.5 py-2.5 text-xs font-medium transition-colors"
				class:text-brand-300={$page.url.pathname === tab.href}
				class:text-slate-500={$page.url.pathname !== tab.href}
			>
				<span class="text-lg leading-none">{tab.icon}</span>
				{tab.label}
			</a>
		{/each}
	</div>
</nav>
