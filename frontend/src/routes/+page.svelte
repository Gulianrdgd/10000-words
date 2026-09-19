<script lang="ts">
	import { api, type DueCard, type ReviewRequest, type ReviewResponse } from '$lib/api';
	import McqCard from '$lib/components/review/McqCard.svelte';
	import TypedCard from '$lib/components/review/TypedCard.svelte';
	import DictationCard from '$lib/components/review/DictationCard.svelte';
	import FreeProductionCard from '$lib/components/review/FreeProductionCard.svelte';
	import SpokenCard from '$lib/components/review/SpokenCard.svelte';
	import ListenCard from '$lib/components/review/ListenCard.svelte';
	import { pronunciationAvailable, type Assessment } from '$lib/pronunciation';
	import FeedbackBanner from '$lib/components/review/FeedbackBanner.svelte';
	import {
		flushQueue,
		loadSessionCards,
		saveSessionCards,
		submitReview,
		sync
	} from '$lib/offline.svelte';
	import { settings } from '$lib/settings.svelte';
	import { prefetch, speechSupported } from '$lib/speech';

	/** How many words "learn extra" unlocks past the daily pace, per press. */
	const EXTRA_NEW_WORDS = 5;

	/** Speaking needs Azure and a live connection; offline falls back to typing. */
	let canSpeak = $state(false);
	/** Resolved before any card renders, so a card can't start typed and then
	 *  be swapped for the spoken one mid-answer, discarding what was typed. */
	let capabilityChecked = $state(false);
	pronunciationAvailable().then(
		(ok) => ((canSpeak = ok), (capabilityChecked = true)),
		() => (capabilityChecked = true)
	);

	/** Set when a card's mic attempt failed and the user asked to type it. */
	let typedFallbackFor = $state<number | null>(null);
	/** The spoken score for the card just answered, shown in the feedback. */
	let lastAssessment = $state<Assessment | null>(null);

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

	// Dictation and listening need audio from somewhere; without any voice at
	// all, fall back to modes that read on screen.
	const current = $derived.by(() => {
		const card = queue[0];
		if (!card) return null;
		// Azure audio needs the network; offline, only a local voice counts, or
		// a listening card would play nothing and have no prompt at all.
		const hasAudio = speechSupported || (canSpeak && sync.online);
		if (card.mode === 5 && !hasAudio) return { ...card, mode: 2 as const };
		if (card.mode === 6 && !hasAudio) return { ...card, mode: 1 as const };
		return card;
	});
	let answering = false;

	async function loadSession(extraNew = 0) {
		loading = true;
		error = null;
		await flushQueue();
		try {
			const res = await api.getDueCards(settings.sessionSize, extraNew);
			queue = res.cards;
			sessionTotal = queue.length;
			dailyNewLimit = res.daily_new_word_limit;
			newIntroducedToday = res.new_words_introduced_today;
			fromCache = false;
			saveSessionCards(queue);
			// warm the audio cache for this session in the background
			prefetch(queue.flatMap((c) => [c.display_lemma, c.sentence?.fr ?? '']));
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
		pronunciationScore?: number;
		phonemes?: { p: string; a: number }[];
		assessment?: Assessment;
		latencyMs: number;
	}) {
		if (!current || answering) return;
		answering = true;
		const body: ReviewRequest = { mode: current.mode, latency_ms: payload.latencyMs };
		if (payload.correct !== undefined) body.correct = payload.correct;
		if (payload.typedAnswer !== undefined) body.typed_answer = payload.typedAnswer;
		if (payload.selfReportedCorrect !== undefined)
			body.self_reported_correct = payload.selfReportedCorrect;
		if (payload.pronunciationScore !== undefined)
			body.pronunciation_score = payload.pronunciationScore;
		if (payload.phonemes !== undefined) body.phonemes = payload.phonemes;
		lastAssessment = payload.assessment ?? null;

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
		typedFallbackFor = null;
		lastAssessment = null;
		feedback = null;
		queue = queue.slice(1);
		saveSessionCards(queue);
	}
</script>

<svelte:head>
	<title>Review — 1000 Mots</title>
</svelte:head>

{#if loading || !capabilityChecked}
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
		<button onclick={() => loadSession()} class="btn-quiet">Try again</button>
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
			{:else if current.mode === 6}
				<ListenCard card={current} onAnswer={handleAnswer} />
			{:else if canSpeak && sync.online && typedFallbackFor !== current.card_id && (current.mode !== 4 || current.sentence)}
				<SpokenCard
					card={current}
					onAnswer={handleAnswer}
					onTypeInstead={() => (typedFallbackFor = current.card_id)}
				/>
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
		<FeedbackBanner result={feedback} card={current} assessment={lastAssessment} onContinue={next} />
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
		{#if !fromCache && dailyNewLimit > 0 && newIntroducedToday >= dailyNewLimit}
			<p class="mt-4 max-w-[34ch] text-sm text-ink-500">
				You've met today's pace of {dailyNewLimit} new word{dailyNewLimit === 1 ? '' : 's'}. Spacing them out is
				what makes them stick — but you can push ahead.
			</p>
		{/if}
		{#if sync.pending > 0}
			<p class="mt-4 text-sm text-bad">
				{sync.pending} review{sync.pending === 1 ? '' : 's'} waiting to sync
			</p>
		{/if}
		<button onclick={() => loadSession()} class="btn-primary mt-8 w-full">
			{reviewedCount > 0 ? `Keep going · ${settings.sessionSize} more` : 'Check again'}
		</button>
		{#if !fromCache && dailyNewLimit > 0 && newIntroducedToday >= dailyNewLimit}
			<button onclick={() => loadSession(EXTRA_NEW_WORDS)} class="btn-quiet mt-2 w-full">
				Learn {EXTRA_NEW_WORDS} extra new words
			</button>
		{/if}
	</div>
{/if}
