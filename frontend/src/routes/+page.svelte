<script lang="ts">
	import { api, type DueCard, type ReviewRequest, type ReviewResponse } from '$lib/api';
	import McqCard from '$lib/components/review/McqCard.svelte';
	import TypedCard from '$lib/components/review/TypedCard.svelte';
	import DictationCard from '$lib/components/review/DictationCard.svelte';
	import FreeProductionCard from '$lib/components/review/FreeProductionCard.svelte';
	import FeedbackBanner from '$lib/components/review/FeedbackBanner.svelte';
	import {
		flushQueue,
		loadSessionCards,
		saveSessionCards,
		submitReview,
		sync
	} from '$lib/offline.svelte';
	import { settings } from '$lib/settings.svelte';
	import { speechSupported } from '$lib/speech';

	let queue = $state<DueCard[]>([]);
	let loading = $state(true);
	let error = $state<string | null>(null);
	let feedback = $state<ReviewResponse | null>(null);
	let reviewedCount = $state(0);
	let masteredCount = $state(0);
	let dailyNewLimit = $state(0);
	let newIntroducedToday = $state(0);
	let fromCache = $state(false);
	let sessionTotal = $state(0);

	// Dictation needs speech synthesis; without it, fall back to plain typed recall.
	const current = $derived.by(() => {
		const card = queue[0];
		if (card && card.mode === 5 && !speechSupported) return { ...card, mode: 2 as const };
		return card ?? null;
	});
	let answering = false;

	async function loadSession() {
		loading = true;
		error = null;
		await flushQueue();
		try {
			const res = await api.getDueCards(settings.sessionSize);
			queue = res.cards;
			sessionTotal = queue.length;
			dailyNewLimit = res.daily_new_word_limit;
			newIntroducedToday = res.new_words_introduced_today;
			fromCache = false;
			saveSessionCards(queue);
		} catch (e) {
			const cached = loadSessionCards();
			if (cached.length > 0) {
				queue = cached;
				sessionTotal = cached.length;
				fromCache = true;
			} else {
				error = (e as Error).message;
			}
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
		if (!current || answering) return;
		answering = true;
		const body: ReviewRequest = { mode: current.mode, latency_ms: payload.latencyMs };
		if (payload.correct !== undefined) body.correct = payload.correct;
		if (payload.typedAnswer !== undefined) body.typed_answer = payload.typedAnswer;
		if (payload.selfReportedCorrect !== undefined)
			body.self_reported_correct = payload.selfReportedCorrect;

		try {
			const result = await submitReview(current, body, payload.typedAnswer);
			feedback = result;
			reviewedCount += 1;
			if (result.word_mastered) masteredCount += 1;
		} catch (e) {
			error = (e as Error).message;
		} finally {
			answering = false;
		}
	}

	function next() {
		feedback = null;
		queue = queue.slice(1);
		saveSessionCards(queue);
	}
</script>

<svelte:head>
	<title>Review — 1000 Mots</title>
</svelte:head>

{#if loading}
	<div class="space-y-8 pt-2" aria-busy="true" aria-label="Loading your session">
		<div class="skeleton h-1.5 w-full rounded-full"></div>
		<div class="flex flex-col items-center gap-5 pt-6">
			<div class="skeleton h-28 w-28 rounded-[1.75rem]"></div>
			<div class="skeleton h-11 w-48"></div>
		</div>
		<div class="space-y-2.5 pt-4">
			{#each [0, 1, 2, 3] as i (i)}
				<div class="skeleton h-[3.25rem] w-full rounded-2xl"></div>
			{/each}
		</div>
	</div>
{:else if error}
	<div class="flex min-h-[60dvh] flex-col items-center justify-center gap-4 text-center">
		<p class="word text-3xl">{sync.online ? 'Serveur injoignable' : 'Pas de connexion'}</p>
		<p class="max-w-[30ch] text-sm text-ink-400">
			{sync.online
				? `Couldn't reach the server: ${error}`
				: "You're offline and there's no saved session on this device yet."}
		</p>
		<button onclick={loadSession} class="btn-quiet">Try again</button>
	</div>
{:else if current}
	<div class="mb-8 space-y-2.5">
		<div class="h-1.5 w-full overflow-hidden rounded-full bg-ink-850">
			<div
				class="h-full rounded-full bg-paper transition-[width] duration-500 ease-out"
				style:width="{sessionTotal ? (100 * (sessionTotal - queue.length)) / sessionTotal : 0}%"
			></div>
		</div>
		<div class="flex items-center justify-between text-xs text-ink-500 tabular">
			<span>{sessionTotal - queue.length} of {sessionTotal}</span>
			{#if fromCache || !sync.online}
				<span class="flex items-center gap-1.5 text-bad">
					<span class="h-1.5 w-1.5 rounded-full bg-bad"></span>
					Offline{sync.pending ? ` · ${sync.pending} to sync` : ''}
				</span>
			{:else}
				<span>{newIntroducedToday}/{dailyNewLimit} new today</span>
			{/if}
		</div>
	</div>

	{#key current.card_id}
		<div class="animate-enter pb-72">
			{#if current.mode === 1}
				<McqCard card={current} onAnswer={handleAnswer} />
			{:else if current.mode === 2 || current.mode === 3}
				<TypedCard card={current} onAnswer={handleAnswer} />
			{:else if current.mode === 5}
				<DictationCard card={current} onAnswer={handleAnswer} />
			{:else}
				<FreeProductionCard card={current} onAnswer={handleAnswer} />
			{/if}
		</div>
	{/key}

	{#if feedback}
		<FeedbackBanner result={feedback} card={current} onContinue={next} />
	{/if}
{:else}
	<div class="flex min-h-[65dvh] animate-enter flex-col justify-center">
		<p class="label">{reviewedCount > 0 ? 'Session complete' : 'Nothing due right now'}</p>
		<h1 class="word mt-2 text-5xl leading-none">
			{reviewedCount > 0 ? 'Bien joué.' : 'Tout est à jour.'}
		</h1>
		{#if reviewedCount > 0}
			<dl class="mt-8 grid grid-cols-2 gap-2.5">
				<div class="surface p-4">
					<dt class="label">Reviewed</dt>
					<dd class="mt-1 text-3xl font-semibold tabular">{reviewedCount}</dd>
				</div>
				<div class="surface p-4">
					<dt class="label">Mastered</dt>
					<dd class="mt-1 text-3xl font-semibold tabular">{masteredCount}</dd>
				</div>
			</dl>
		{:else}
			<p class="mt-4 max-w-[34ch] text-ink-400">
				New words unlock each day based on your weekly goal. Come back later, or check again now.
			</p>
		{/if}
		{#if sync.pending > 0}
			<p class="mt-4 text-sm text-bad">
				{sync.pending} review{sync.pending === 1 ? '' : 's'} waiting to sync
			</p>
		{/if}
		<button onclick={loadSession} class="btn-primary mt-8 w-full">
			{reviewedCount > 0 ? `Keep going · ${settings.sessionSize} more` : 'Check again'}
		</button>
	</div>
{/if}
