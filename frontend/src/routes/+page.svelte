<script lang="ts">
	import { api, type DueCard, type ReviewRequest, type ReviewResponse } from '$lib/api';
	import McqCard from '$lib/components/review/McqCard.svelte';
	import TypedCard from '$lib/components/review/TypedCard.svelte';
	import FreeProductionCard from '$lib/components/review/FreeProductionCard.svelte';
	import FeedbackBanner from '$lib/components/review/FeedbackBanner.svelte';

	let queue = $state<DueCard[]>([]);
	let loading = $state(true);
	let error = $state<string | null>(null);
	let feedback = $state<ReviewResponse | null>(null);
	let reviewedCount = $state(0);
	let masteredCount = $state(0);
	let dailyNewLimit = $state(0);
	let newIntroducedToday = $state(0);
	let sessionStarted = $state(false);

	const current = $derived(queue[0] ?? null);

	async function loadSession() {
		loading = true;
		error = null;
		try {
			const res = await api.getDueCards(20);
			queue = res.cards;
			dailyNewLimit = res.daily_new_word_limit;
			newIntroducedToday = res.new_words_introduced_today;
			sessionStarted = true;
		} catch (e) {
			error = (e as Error).message;
		} finally {
			loading = false;
		}
	}

	loadSession();

	async function handleAnswer(payload: {
		correct?: boolean;
		typedAnswer?: string;
		selfReportedCorrect?: boolean;
		latencyMs: number;
	}) {
		if (!current) return;
		const body: ReviewRequest = { mode: current.mode, latency_ms: payload.latencyMs };
		if (payload.correct !== undefined) body.correct = payload.correct;
		if (payload.typedAnswer !== undefined) body.typed_answer = payload.typedAnswer;
		if (payload.selfReportedCorrect !== undefined)
			body.self_reported_correct = payload.selfReportedCorrect;

		try {
			const result = await api.submitReview(current.card_id, body);
			feedback = result;
			reviewedCount += 1;
			if (result.word_mastered) masteredCount += 1;
		} catch (e) {
			error = (e as Error).message;
		}
	}

	function next() {
		feedback = null;
		queue = queue.slice(1);
	}
</script>

<svelte:head>
	<title>Review — 1000 Mots</title>
</svelte:head>

{#if loading}
	<div class="flex h-64 items-center justify-center text-slate-500">Loading your session…</div>
{:else if error}
	<div class="space-y-3 text-center">
		<p class="text-rose-400">{error}</p>
		<p class="text-xs text-slate-500">
			Is the backend running? Check <code>VITE_API_BASE_URL</code>.
		</p>
		<button onclick={loadSession} class="rounded-xl bg-brand-500 px-4 py-2 text-white">Retry</button
		>
	</div>
{:else if current}
	<div class="mb-4 flex items-center justify-between text-xs text-slate-500">
		<span>{queue.length} card{queue.length === 1 ? '' : 's'} left</span>
		<span>{newIntroducedToday}/{dailyNewLimit} new words today</span>
	</div>

	{#key current.card_id}
		<div class="pb-32">
			{#if current.mode === 1}
				<McqCard card={current} onAnswer={handleAnswer} />
			{:else if current.mode === 2 || current.mode === 3}
				<TypedCard card={current} onAnswer={handleAnswer} />
			{:else}
				<FreeProductionCard card={current} onAnswer={handleAnswer} />
			{/if}
		</div>
	{/key}

	{#if feedback}
		<FeedbackBanner result={feedback} onContinue={next} />
	{/if}
{:else}
	<div class="flex h-64 flex-col items-center justify-center gap-3 text-center">
		<p class="text-4xl">🎉</p>
		<p class="text-lg font-medium text-slate-100">All caught up!</p>
		<p class="text-sm text-slate-500">
			{reviewedCount} card{reviewedCount === 1 ? '' : 's'} reviewed{masteredCount > 0
				? ` · ${masteredCount} word${masteredCount === 1 ? '' : 's'} mastered`
				: ''}
		</p>
		<button onclick={loadSession} class="mt-2 rounded-xl bg-brand-500 px-4 py-2 text-white">
			Check for more
		</button>
	</div>
{/if}
