<script lang="ts">
	import type { DueCard } from '$lib/api';
	import PromptLabel from './PromptLabel.svelte';

	let {
		card,
		onAnswer
	}: {
		card: DueCard;
		onAnswer: (result: { typedAnswer: string; latencyMs: number }) => void;
	} = $props();

	let value = $state('');
	let answered = $state(false);
	let inputEl: HTMLInputElement | undefined = $state();
	const shownAt = Date.now();

	const needsArticle = $derived(
		card.mode !== 3 && card.pos === 'noun' && (card.gender === 'm' || card.gender === 'f')
	);

	// render the cloze blank as an underlined gap rather than literal underscores
	const clozeParts = $derived(card.cloze_sentence?.split('____') ?? []);

	$effect(() => {
		inputEl?.focus();
	});

	function submit() {
		if (answered || !value.trim()) return;
		answered = true;
		onAnswer({ typedAnswer: value.trim(), latencyMs: Date.now() - shownAt });
	}
</script>

<div class="space-y-9">
	<div class="space-y-6">
		{#if card.mode === 3 && card.cloze_sentence}
			<PromptLabel text="Complete the sentence" pos={card.pos} />
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
			<PromptLabel text="How do you say this in French?" pos={card.pos} />
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

	<form
		class="space-y-3"
		onsubmit={(e) => {
			e.preventDefault();
			submit();
		}}
	>
		<input
			bind:this={inputEl}
			bind:value
			readonly={answered}
			type="text"
			autocomplete="off"
			autocapitalize="off"
			spellcheck="false"
			lang="fr"
			placeholder={needsArticle ? 'la maison, un arbre…' : 'Écris en français…'}
			class="field font-serif text-xl"
		/>
		<button type="submit" class="btn-primary w-full" disabled={!value.trim() || answered}>
			Check
		</button>
	</form>
</div>
