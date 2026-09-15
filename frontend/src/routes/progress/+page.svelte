<script lang="ts">
	import { api, type GrowthResponse, type WordProgress } from '$lib/api';
	import GrowthChart from '$lib/components/GrowthChart.svelte';

	let growth = $state<GrowthResponse | null>(null);
	let words = $state<WordProgress[]>([]);
	let loading = $state(true);
	let error = $state<string | null>(null);
	let filter = $state<'all' | 'mastered' | 'learning' | 'new'>('all');

	async function load() {
		loading = true;
		error = null;
		try {
			const [g, w] = await Promise.all([api.getGrowth(), api.getWords()]);
			growth = g;
			words = w;
		} catch (e) {
			error = (e as Error).message;
		} finally {
			loading = false;
		}
	}

	load();

	const filtered = $derived(
		words.filter((w) => {
			if (filter === 'mastered') return w.mastered;
			if (filter === 'new') return w.recognition_mastery === 0 && w.production_mastery === 0;
			if (filter === 'learning')
				return !w.mastered && (w.recognition_mastery > 0 || w.production_mastery > 0);
			return true;
		})
	);
</script>

<svelte:head>
	<title>Progress — 1000 Mots</title>
</svelte:head>

<h1 class="mb-6 text-2xl font-semibold text-slate-50">Progress</h1>

{#if loading}
	<p class="text-slate-500">Loading…</p>
{:else if error}
	<p class="text-rose-400">{error}</p>
{:else if growth}
	<div class="space-y-6">
		<section class="grid grid-cols-2 gap-3">
			<div class="rounded-2xl border border-slate-800 bg-slate-900 p-4 text-center">
				<p class="text-2xl font-semibold text-slate-50">{growth.coverage_percent}%</p>
				<p class="text-xs text-slate-500">of core vocabulary</p>
			</div>
			<div class="rounded-2xl border border-slate-800 bg-slate-900 p-4 text-center">
				<p class="text-2xl font-semibold text-slate-50">🔥 {growth.current_streak}</p>
				<p class="text-xs text-slate-500">day streak (best {growth.longest_streak})</p>
			</div>
		</section>

		<section class="rounded-2xl border border-slate-800 bg-slate-900 p-4">
			<p class="mb-2 text-sm font-medium text-slate-200">Words mastered over time</p>
			{#if growth.points.length > 0}
				<GrowthChart points={growth.points} />
			{:else}
				<p class="py-10 text-center text-sm text-slate-500">
					Master your first word to start the chart.
				</p>
			{/if}
		</section>

		<section>
			<div class="mb-3 flex gap-2 overflow-x-auto text-xs">
				{#each [['all', 'All'], ['mastered', 'Mastered'], ['learning', 'Learning'], ['new', 'Not started']] as [key, label] (key)}
					<button
						onclick={() => (filter = key as typeof filter)}
						class="whitespace-nowrap rounded-full px-3 py-1.5 font-medium"
						class:bg-brand-500={filter === key}
						class:text-white={filter === key}
						class:bg-slate-800={filter !== key}
						class:text-slate-400={filter !== key}
					>
						{label}
					</button>
				{/each}
			</div>

			<div class="divide-y divide-slate-800 rounded-2xl border border-slate-800 bg-slate-900">
				{#each filtered.slice(0, 60) as w (w.id)}
					<div class="flex items-center justify-between px-4 py-2.5">
						<div>
							<p class="text-sm text-slate-100">{w.lemma}</p>
							<p class="text-xs text-slate-500">{w.translation_en}</p>
						</div>
						<div class="flex items-center gap-1.5 text-xs">
							{#if w.mastered}
								<span class="rounded-full bg-emerald-500/15 px-2 py-0.5 text-emerald-300"
									>mastered</span
								>
							{:else}
								<span class="text-slate-500">R{w.recognition_mastery} · P{w.production_mastery}</span
								>
							{/if}
						</div>
					</div>
				{/each}
				{#if filtered.length === 0}
					<p class="px-4 py-6 text-center text-sm text-slate-500">No words in this category yet.</p>
				{/if}
			</div>
			{#if filtered.length > 60}
				<p class="mt-2 text-center text-xs text-slate-600">
					Showing 60 of {filtered.length} words
				</p>
			{/if}
		</section>
	</div>
{/if}
