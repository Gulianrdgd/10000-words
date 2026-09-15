<script lang="ts">
	import { api, type GoalResponse, type WeekReviewResponse } from '$lib/api';
	import { addDays, weekStartISO } from '$lib/date';

	let goal = $state<GoalResponse | null>(null);
	let lastWeek = $state<WeekReviewResponse | null>(null);
	let thisWeek = $state<WeekReviewResponse | null>(null);
	let draftTarget = $state(20);
	let loading = $state(true);
	let saving = $state(false);
	let error = $state<string | null>(null);

	async function load() {
		loading = true;
		error = null;
		try {
			const currentWs = weekStartISO();
			const prevWs = addDays(currentWs, -7);
			const [g, lw, tw] = await Promise.all([
				api.getCurrentGoal(),
				api.getWeekReview(prevWs),
				api.getWeekReview(currentWs)
			]);
			goal = g;
			draftTarget = g.target_words;
			lastWeek = lw;
			thisWeek = tw;
		} catch (e) {
			error = (e as Error).message;
		} finally {
			loading = false;
		}
	}

	load();

	async function saveGoal() {
		saving = true;
		try {
			goal = await api.setGoal(draftTarget);
		} finally {
			saving = false;
		}
	}
</script>

<svelte:head>
	<title>Goals — 1000 Mots</title>
</svelte:head>

<h1 class="mb-6 text-2xl font-semibold text-slate-50">Weekly goal</h1>

{#if loading}
	<p class="text-slate-500">Loading…</p>
{:else if error}
	<p class="text-rose-400">{error}</p>
{:else}
	<div class="space-y-8">
		<section class="rounded-2xl border border-slate-800 bg-slate-900 p-5">
			<p class="text-sm text-slate-400">Words to master this week</p>
			<div class="mt-3 flex items-center gap-4">
				<input
					type="range"
					min="5"
					max="60"
					step="5"
					bind:value={draftTarget}
					class="flex-1 accent-brand-400"
				/>
				<span class="w-10 text-right text-xl font-semibold text-slate-50">{draftTarget}</span>
			</div>
			{#if lastWeek}
				<p class="mt-2 text-xs text-slate-500">
					Last week you mastered {lastWeek.achieved_words} word{lastWeek.achieved_words === 1
						? ''
						: 's'}.
				</p>
			{/if}
			<button
				onclick={saveGoal}
				disabled={saving}
				class="mt-4 w-full rounded-xl bg-brand-500 py-2.5 font-medium text-white disabled:opacity-50"
			>
				{saving ? 'Saving…' : 'Save goal'}
			</button>
		</section>

		{#if goal}
			<section class="rounded-2xl border border-slate-800 bg-slate-900 p-5">
				<p class="text-sm text-slate-400">This week so far</p>
				<div class="mt-2 flex items-end gap-2">
					<span class="text-3xl font-semibold text-slate-50">{goal.achieved_words}</span>
					<span class="pb-1 text-slate-500">/ {goal.target_words} words mastered</span>
				</div>
				<div class="mt-3 h-2 w-full overflow-hidden rounded-full bg-slate-800">
					<div
						class="h-full rounded-full bg-brand-400"
						style="width: {Math.min(100, (100 * goal.achieved_words) / Math.max(1, goal.target_words))}%"
					></div>
				</div>
				<p class="mt-2 text-xs text-slate-500">{goal.days_remaining} days left this week</p>
			</section>
		{/if}

		{#if lastWeek && (lastWeek.mastered_words.length > 0 || lastWeek.shaky_words.length > 0)}
			<section class="rounded-2xl border border-slate-800 bg-slate-900 p-5">
				<p class="text-sm font-medium text-slate-200">Last week's review</p>
				<p class="mt-2 text-sm text-slate-400">{lastWeek.growth_stat}</p>

				{#if lastWeek.mastered_words.length > 0}
					<div class="mt-4">
						<p class="text-xs uppercase tracking-wide text-slate-500">Mastered</p>
						<div class="mt-2 flex flex-wrap gap-2">
							{#each lastWeek.mastered_words as w (w)}
								<span class="rounded-full bg-emerald-500/15 px-2.5 py-1 text-xs text-emerald-300"
									>{w}</span
								>
							{/each}
						</div>
					</div>
				{/if}

				{#if lastWeek.shaky_words.length > 0}
					<div class="mt-4">
						<p class="text-xs uppercase tracking-wide text-slate-500">Still shaky</p>
						<div class="mt-2 flex flex-wrap gap-2">
							{#each lastWeek.shaky_words as w (w)}
								<span class="rounded-full bg-amber-500/15 px-2.5 py-1 text-xs text-amber-300"
									>{w}</span
								>
							{/each}
						</div>
					</div>
				{/if}
			</section>
		{/if}

		{#if thisWeek}
			<section class="rounded-2xl border border-slate-800 bg-slate-900 p-5">
				<p class="text-sm font-medium text-slate-200">Growth</p>
				<p class="mt-2 text-sm text-slate-400">{thisWeek.growth_stat}</p>
			</section>
		{/if}
	</div>
{/if}
