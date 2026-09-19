<script lang="ts">
	import '../app.css';
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import { getToken } from '$lib/api';
	import BottomNav from '$lib/components/BottomNav.svelte';
	import { flushQueue, sync } from '$lib/offline.svelte';

	let { children } = $props();

	const onLogin = $derived($page.url.pathname === '/login');
	const signedIn = $derived(onLogin || !!getToken());

	$effect(() => {
		if (!signedIn) goto('/login');
	});

	// Retry queued offline reviews periodically too: the 'online' event doesn't
	// fire when the network was fine but the server was unreachable.
	$effect(() => {
		const timer = setInterval(() => {
			if (sync.pending > 0) flushQueue();
		}, 30_000);
		return () => clearInterval(timer);
	});
</script>

{#if signedIn}
	<div class="relative z-[1] mx-auto flex min-h-[100dvh] max-w-md flex-col pb-20 sm:pb-24">
		<main class="flex-1 px-5 pt-[max(1.5rem,env(safe-area-inset-top))]">
			{@render children()}
		</main>
	</div>

	{#if !onLogin}
		<BottomNav />
	{/if}
{/if}
