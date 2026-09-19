<script lang="ts">
	// Production modes answered out loud instead of typed. Azure transcribes
	// what was said and scores how it was said; the server grades the words with
	// the same rules as a typed answer, then fails anything mumbled.
	import type { DueCard } from '$lib/api';
	import type { Assessment } from '$lib/pronunciation';
	import { createRecorder } from '$lib/recorder.svelte';
	import PromptLabel from './PromptLabel.svelte';

	let {
		card,
		onAnswer,
		onTypeInstead
	}: {
		card: DueCard;
		/** Escape hatch: without it a blocked microphone strands every card. */
		onTypeInstead: () => void;
		onAnswer: (result: {
			typedAnswer: string;
			pronunciationScore: number;
			phonemes: { p: string; a: number }[];
			assessment: Assessment;
			latencyMs: number;
		}) => void;
	} = $props();

	let answered = $state(false);
	const shownAt = Date.now();

	const needsArticle = $derived(
		card.mode !== 3 && card.pos === 'noun' && (card.gender === 'm' || card.gender === 'f')
	);
	const clozeParts = $derived(card.cloze_sentence?.split('____') ?? []);
	// mode 4 reads a whole sentence aloud, where fluency and completeness
	// actually mean something; the others target the single word
	const expected = $derived(
		card.mode === 4 ? (card.sentence?.fr ?? card.display_lemma) : (card.expected_answer ?? card.lemma)
	);

	/** Azure returns display text ("La maison.") — the server grades bare words. */
	function normalize(text: string) {
		return text
			.toLowerCase()
			.replace(/[’']/g, "'")
			.replace(/[.,!?;:«»"]/g, '')
			.trim();
	}

	const recorder = createRecorder((result) => {
		answered = true;
		onAnswer({
			typedAnswer: normalize(result.recognized),
			pronunciationScore: result.pronunciation,
			phonemes: result.words.flatMap((w) =>
				w.phonemes.map((p) => ({ p: p.phoneme, a: p.accuracy }))
			),
			assessment: result,
			latencyMs: Date.now() - shownAt
		});
	});

	$effect(() => recorder.dispose);
</script>

<div class="space-y-6 sm:space-y-9">
	<div class="space-y-6">
		{#if card.mode === 4 && card.sentence}
			<PromptLabel text="Read this out loud" pos={card.pos} />
			<div class="space-y-3 text-center">
				<!-- a full sentence at 28px wraps to five lines on a narrow phone -->
				<p class="font-serif text-xl leading-snug text-ink-100 sm:text-[1.75rem]">
					{card.sentence.fr}
				</p>
				<p class="text-ink-400">{card.sentence.en}</p>
			</div>
		{:else if card.mode === 3 && card.cloze_sentence}
			<PromptLabel text="Say the missing word" pos={card.pos} />
			<h2 class="word text-center text-[2rem] leading-tight">
				{#each clozeParts as part, i (i)}{part}{#if i < clozeParts.length - 1}<span
							class="mx-1 inline-block w-20 translate-y-1 border-b-2 border-paper/70"
							aria-label="blank"
						></span>{/if}{/each}
			</h2>
			{#if card.sentence}
				<p class="text-center text-ink-400">{card.sentence.en}</p>
			{/if}
		{:else}
			<PromptLabel text="Say this in French" pos={card.pos} />
			<div class="flex flex-col items-center text-center">
				{#if card.emoji}
					<div
						class="grid h-24 w-24 place-items-center rounded-[1.75rem] bg-ink-900 text-5xl ring-1 ring-inset ring-ink-800"
						aria-hidden="true"
					>
						{card.emoji}
					</div>
				{/if}
				<h2 class="text-4xl font-semibold tracking-tight text-ink-100" class:mt-5={!!card.emoji}>
					{card.translation_en}
				</h2>
				{#if needsArticle}
					<p class="mt-3 text-sm text-ink-500">
						With its article — <span class="text-masc">le</span>/<span class="text-fem">la</span>
						or <span class="text-masc">un</span>/<span class="text-fem">une</span>
					</p>
				{/if}
			</div>
		{/if}
	</div>

	<div class="space-y-3">
		<button
			type="button"
			onclick={() => recorder.toggle(expected)}
			disabled={answered || recorder.scoring}
			class="btn-primary flex w-full items-center justify-center gap-2.5 {recorder.recording
				? 'animate-pulse'
				: ''}"
		>
			{#if recorder.recording}
				<svg viewBox="0 0 24 24" fill="currentColor" class="h-4 w-4" aria-hidden="true">
					<rect x="6" y="6" width="12" height="12" rx="2" />
				</svg>
				Stop
			{:else}
				<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" class="h-5 w-5" aria-hidden="true">
					<rect x="9" y="2" width="6" height="11" rx="3" />
					<path d="M5 11a7 7 0 0 0 14 0M12 18v4" />
				</svg>
				{recorder.scoring ? 'Scoring…' : 'Speak'}
			{/if}
		</button>
		{#if recorder.error}
			<button type="button" onclick={onTypeInstead} class="btn-quiet w-full py-2.5 text-sm">
				Type it instead
			</button>
		{/if}
		<p class="text-center text-sm text-ink-500" role="status">
			{#if recorder.error}
				<span class="text-bad">{recorder.error}</span>
			{:else if recorder.recording}
				Say it, then press Stop.
			{:else if recorder.scoring}
				Sending to Azure…
			{:else}
				Press Speak, say the word, then press Stop.
			{/if}
		</p>
	</div>
</div>
