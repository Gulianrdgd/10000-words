<script lang="ts">
	import '../app.css';
	import BottomNav from '$lib/components/BottomNav.svelte';

	let { children } = $props();
</script>

<div class="mx-auto flex min-h-screen max-w-md flex-col pb-16">
	<main class="flex-1 px-4 pt-6">
		{@render children()}
	</main>
</div>

<BottomNav />
