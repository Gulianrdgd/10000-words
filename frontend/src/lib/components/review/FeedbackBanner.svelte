<script lang="ts">
	import type { DueCard, ReviewResponse } from '$lib/api';
	import type { Assessment } from '$lib/pronunciation';
	import ArticleWord from '$lib/components/ArticleWord.svelte';
	import SpeakButton from '$lib/components/SpeakButton.svelte';
	import { settings } from '$lib/settings.svelte';
	import { isSpeakShortcut, speak } from '$lib/speech';

	let {
		result,
		card,
		assessment = null,
		onContinue
	}: {
		result: ReviewResponse;
		card: DueCard;
		/** Present when the answer was spoken: what Azure heard and scored. */
		assessment?: Assessment | null;
		onContinue: () => void;
	} = $props();

	const tone = (score: number) =>
		score >= 80 ? 'text-good' : score >= 60 ? 'text-ink-200' : 'text-bad';

	// What to read aloud: the full sentence for cloze, otherwise the word with its article.
	const audioText = $derived(
		card.mode === 3 && card.sentence ? card.sentence.fr : (result.expected_answer ?? card.display_lemma)
	);
	const showAnswer = $derived(!!result.expected_answer && (!result.correct || result.near_miss));

	$effect(() => {
		// MCQ already spoke the word when the card appeared; dictation just played it
		if (settings.autoplayAudio && card.mode !== 1 && card.mode !== 5) speak(audioText);
	});

	function onkeydown(e: KeyboardEvent) {
		if (e.key === 'Enter' && (e.target as HTMLElement)?.tagName !== 'TEXTAREA') {
			e.preventDefault();
			onContinue();
		} else if (isSpeakShortcut(e)) {
			e.preventDefault();
			speak(audioText);
		}
	}
</script>

<svelte:window {onkeydown} />

<div class="fixed inset-x-0 bottom-[calc(4rem+env(safe-area-inset-bottom))] z-10 animate-rise px-3 pb-2" role="status">
	<div
		class="mx-auto max-w-md rounded-card bg-ink-900/95 p-4 shadow-[0_-12px_40px_-12px_rgba(0,0,0,0.7)] ring-1 ring-inset backdrop-blur-md {result.correct
			? 'ring-good/40'
			: 'ring-bad/40'}"
	>
		<div class="flex items-center justify-between">
			<p class="flex items-center gap-2 text-[0.9375rem] font-semibold {result.correct ? 'text-good' : 'text-bad'}">
				<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.25" stroke-linecap="round" stroke-linejoin="round" class="h-4 w-4" aria-hidden="true">
					{#if result.correct}<path d="m5 12.5 4.5 4.5L19 7.5" />{:else}<path d="M12 7v6m0 4h.01" />{/if}
				</svg>
				{#if result.correct}
					{result.near_miss ? 'Close enough' : 'Correct'}
				{:else if result.gender_correct === false}
					Check the gender
				{:else}
					Not quite
				{/if}
			</p>
			{#if result.word_mastered}
				<span class="rounded-md bg-paper/10 px-2 py-0.5 text-xs font-medium text-paper">Word mastered</span>
			{/if}
		</div>

		<div class="mt-3 flex items-center gap-3">
			{#if card.emoji}
				<span class="grid h-12 w-12 shrink-0 place-items-center rounded-xl bg-ink-850 text-2xl" aria-hidden="true">{card.emoji}</span>
			{/if}
			<div class="min-w-0 flex-1">
				{#if showAnswer}
					<p class="word truncate text-2xl">
						<ArticleWord text={result.expected_answer ?? ''} lemma={card.lemma} gender={card.gender} />
					</p>
					<p class="truncate text-sm text-ink-400">
						{card.translation_en}{#if result.gender_correct === false}
							· {card.gender === 'm' ? 'masculine' : 'feminine'}{/if}
					</p>
				{:else}
					<p class="word truncate text-2xl">
						<ArticleWord text={card.display_lemma} lemma={card.lemma} gender={card.gender} />
					</p>
					<p class="truncate text-sm text-ink-400">{card.translation_en}</p>
				{/if}
			</div>
			<SpeakButton text={audioText} size="sm" />
		</div>

		{#if assessment}
			<div class="mt-3 rounded-xl bg-ink-950/60 p-3">
				<div class="flex items-baseline justify-between">
					<p class="label">Pronunciation</p>
					<p class="tabular">
						<span class="text-2xl font-semibold {tone(assessment.pronunciation)}">
							{assessment.pronunciation}
						</span><span class="text-xs text-ink-500"> / 100</span>
					</p>
				</div>
				<dl class="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-ink-500 tabular">
					{#each [['accuracy', assessment.accuracy], ['fluency', assessment.fluency], ['complete', assessment.completeness]] as [name, score] (name)}
						<div class="flex gap-1">
							<dt>{name}</dt>
							<dd class={tone(score as number)}>{score}</dd>
						</div>
					{/each}
				</dl>
				{#if assessment.words.length > 0}
					<!-- a read-aloud sentence can run to a dozen words; cap the height so
				     the banner can't grow taller than the card it reports on -->
				<p class="mt-2.5 flex max-h-24 flex-wrap items-baseline gap-x-2 gap-y-1 overflow-y-auto">
						{#each assessment.words as w (w.word)}
							<span class="font-serif text-lg {tone(w.accuracy)}">
								{w.word}<span class="ml-0.5 text-[0.6875rem] opacity-70 tabular">{w.accuracy}</span>
							</span>
						{/each}
					</p>
				{/if}
				{#if assessment.recognized}
					<p class="mt-1.5 truncate text-xs text-ink-500">Heard: “{assessment.recognized}”</p>
				{/if}
			</div>
		{/if}

		<div class="mt-3 flex items-center justify-between text-xs text-ink-500 tabular">
			{#if result.offline}
				<span>Saved offline · syncs when you reconnect</span>
			{:else}
				<span>Next review in {result.interval_days} day{result.interval_days === 1 ? '' : 's'}</span>
				<span>{result.streak} day streak</span>
			{/if}
		</div>

		<button onclick={onContinue} class="btn-primary mt-3 w-full">
			Continue <kbd class="hidden text-xs opacity-50 sm:inline">↵</kbd>
		</button>
	</div>
</div>
