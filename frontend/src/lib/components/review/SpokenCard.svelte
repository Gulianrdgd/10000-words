<script lang="ts">
	// Production modes answered out loud instead of typed. Azure transcribes
	// what was said and scores how it was said; the server grades the words with
	// the same rules as a typed answer, then fails anything mumbled.
	import type { DueCard } from '$lib/api';
	import { assess } from '$lib/pronunciation';
	import PromptLabel from './PromptLabel.svelte';

	let {
		card,
		onAnswer
	}: {
		card: DueCard;
		onAnswer: (result: {
			typedAnswer: string;
			pronunciationScore: number;
			phonemes: { p: string; a: number }[];
			latencyMs: number;
		}) => void;
	} = $props();

	let listening = $state(false);
	let answered = $state(false);
	let error = $state<string | null>(null);
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

	async function listen() {
		if (answered || listening) return;
		listening = true;
		error = null;
		try {
			const result = await assess(expected);
			answered = true;
			onAnswer({
				typedAnswer: normalize(result.recognized),
				pronunciationScore: result.pronunciation,
				phonemes: result.words.flatMap((w) =>
					w.phonemes.map((p) => ({ p: p.phoneme, a: p.accuracy }))
				),
				latencyMs: Date.now() - shownAt
			});
		} catch (e) {
			error = (e as Error).message;
		} finally {
			listening = false;
		}
	}
</script>

<div class="space-y-9">
	<div class="space-y-6">
		{#if card.mode === 4 && card.sentence}
			<PromptLabel text="Read this out loud" pos={card.pos} />
			<div class="space-y-3 text-center">
				<p class="font-serif text-[1.75rem] leading-snug text-ink-100">{card.sentence.fr}</p>
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
			onclick={listen}
			disabled={answered}
			class="btn-primary flex w-full items-center justify-center gap-2.5 {listening
				? 'animate-pulse'
				: ''}"
		>
			<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" class="h-5 w-5" aria-hidden="true">
				<rect x="9" y="2" width="6" height="11" rx="3" />
				<path d="M5 11a7 7 0 0 0 14 0M12 18v4" />
			</svg>
			{listening ? 'Listening…' : 'Speak'}
		</button>
		<p class="text-center text-sm text-ink-500" role="status">
			{#if error}
				<span class="text-bad">{error}</span>
			{:else if listening}
				Say it out loud, then pause.
			{:else}
				Press, then say the word.
			{/if}
		</p>
	</div>
</div>
