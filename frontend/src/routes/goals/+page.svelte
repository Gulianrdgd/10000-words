<script lang="ts">
	import { api, type GoalResponse, type WeekReviewResponse } from '$lib/api';
	import { addDays, weekStartISO } from '$lib/date';

	let goal = $state<GoalResponse | null>(null);
	let lastWeek = $state<WeekReviewResponse | null>(null);
	let thisWeek = $state<WeekReviewResponse | null>(null);
	let draftTarget = $state(20);
	let loading = $state(true);
	let saving = $state(false);
	let saved = $state(false);
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
		error = null;
		try {
			goal = await api.setGoal(draftTarget);
			saved = true;
			setTimeout(() => (saved = false), 1800);
		} catch (e) {
			// without this the failure was silent and the promise unhandled
			error = (e as Error).message;
		} finally {
			saving = false;
		}
	}

	const pct = $derived(goal ? Math.min(100, (100 * goal.achieved_words) / Math.max(1, goal.target_words)) : 0);
	const perDay = $derived(Math.max(1, Math.ceil(draftTarget / 7)));
</script>

<svelte:head>
	<title>Goals — 1000 Mots</title>
</svelte:head>

<h1 class="word text-4xl">This week</h1>

{#if loading}
	<div class="mt-6 space-y-3" aria-busy="true">
		<div class="skeleton h-44"></div>
		<div class="skeleton h-40"></div>
	</div>
{:else if error}
	<p class="mt-6 text-bad">{error}</p>
{:else}
	<div class="mt-6 space-y-3 animate-enter">
		{#if goal}
			<section class="surface flex items-center gap-5 p-5">
				<svg viewBox="0 0 64 64" class="h-24 w-24 shrink-0 -rotate-90" aria-hidden="true">
					<circle cx="32" cy="32" r="27" fill="none" stroke-width="6" class="stroke-ink-800" />
					<circle
						cx="32"
						cy="32"
						r="27"
						fill="none"
						stroke-width="6"
						stroke-linecap="round"
						class="stroke-paper transition-[stroke-dashoffset] duration-700 ease-out"
						stroke-dasharray={2 * Math.PI * 27}
						stroke-dashoffset={2 * Math.PI * 27 * (1 - pct / 100)}
					/>
				</svg>
				<div>
					<p class="text-4xl font-semibold tracking-tight tabular">
						{goal.achieved_words}<span class="text-lg font-normal text-ink-500"> / {goal.target_words}</span>
					</p>
					<p class="mt-1 text-sm text-ink-400">words mastered</p>
					<p class="mt-2 text-xs text-ink-500 tabular">
						{goal.days_remaining} day{goal.days_remaining === 1 ? '' : 's'} left
					</p>
				</div>
			</section>
		{/if}

		<section class="surface p-5">
			<div class="flex items-baseline justify-between">
				<p class="label">Weekly target</p>
				<p class="text-3xl font-semibold tabular">{draftTarget}</p>
			</div>
			<input
				type="range"
				min="5"
				max="60"
				step="5"
				bind:value={draftTarget}
				aria-label="Words to master per week"
				class="mt-4 w-full accent-[#f1e6cf]"
			/>
			<p class="mt-2 text-xs text-ink-500">
				About {perDay} new word{perDay === 1 ? '' : 's'} a day.{#if lastWeek}{` Last week you mastered ${lastWeek.achieved_words}.`}{/if}
			</p>
			<button
				onclick={saveGoal}
				disabled={saving || (goal?.target_words === draftTarget && !saved)}
				class="btn-primary mt-4 w-full"
			>
				{saving ? 'Saving…' : saved ? 'Saved' : 'Save target'}
			</button>
		</section>

		{#if lastWeek && (lastWeek.mastered_words.length > 0 || lastWeek.shaky_words.length > 0)}
			<section class="surface p-5">
				<h2 class="word text-2xl">Last week</h2>
				<p class="mt-2 max-w-[48ch] text-sm text-ink-400">{lastWeek.growth_stat}</p>

				{#if lastWeek.mastered_words.length > 0}
					<p class="label mt-5">Mastered</p>
					<div class="mt-2 flex flex-wrap gap-1.5">
						{#each lastWeek.mastered_words as w (w)}
							<span class="rounded-lg bg-good/10 px-2.5 py-1 font-serif text-good">{w}</span>
						{/each}
					</div>
				{/if}

				{#if lastWeek.shaky_words.length > 0}
					<p class="label mt-5">Still shaky</p>
					<div class="mt-2 flex flex-wrap gap-1.5">
						{#each lastWeek.shaky_words as w (w)}
							<span class="rounded-lg bg-bad/10 px-2.5 py-1 font-serif text-bad">{w}</span>
						{/each}
					</div>
				{/if}
			</section>
		{:else if thisWeek}
			<p class="px-1 pt-2 text-sm text-ink-500">{thisWeek.growth_stat}</p>
		{/if}
	</div>
{/if}
