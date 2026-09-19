<script lang="ts">
	import type { DueCard } from '$lib/api';
	import WordHero from '$lib/components/WordHero.svelte';
	import PromptLabel from './PromptLabel.svelte';
	import { settings } from '$lib/settings.svelte';
	import { isSpeakShortcut, isTypingTarget, speak } from '$lib/speech';

	let {
		card,
		onAnswer
	}: {
		card: DueCard;
		onAnswer: (result: { correct: boolean; latencyMs: number; picked: string }) => void;
	} = $props();

	let picked = $state<string | null>(null);
	const shownAt = Date.now();

	$effect(() => {
		if (settings.autoplayAudio) speak(card.display_lemma);
	});

	function choose(option: string) {
		if (picked !== null) return;
		picked = option;
		const correct = option === card.translation_en;
		onAnswer({ correct, latencyMs: Date.now() - shownAt, picked: option });
	}

	function onkeydown(e: KeyboardEvent) {
		if (isSpeakShortcut(e)) {
			e.preventDefault();
			speak(card.display_lemma);
			return;
		}
		if (picked !== null || isTypingTarget(e.target) || e.metaKey || e.ctrlKey || e.altKey) return;
		const index = Number(e.key) - 1;
		const options = card.options ?? [];
		if (Number.isInteger(index) && index >= 0 && index < options.length) {
			e.preventDefault();
			choose(options[index]);
		}
	}

	function optionClass(option: string) {
		if (picked === null) return 'bg-ink-900 ring-ink-800 hover:bg-ink-850 hover:ring-ink-700';
		if (option === card.translation_en) return 'bg-good/15 ring-good/60 text-ink-100';
		if (option === picked) return 'bg-bad/15 ring-bad/60 text-ink-100';
		return 'bg-ink-900 ring-ink-800 opacity-40';
	}
</script>

<svelte:window {onkeydown} />

<div class="space-y-6 sm:space-y-9">
	<div class="space-y-4 sm:space-y-6">
		<PromptLabel text="What does this mean?" pos={card.pos} />
		<WordHero lemma={card.lemma} displayLemma={card.display_lemma} gender={card.gender} emoji={card.emoji} />
		{#if card.sentence}
			<p class="mx-auto max-w-[32ch] text-center font-serif text-lg italic leading-snug text-ink-400">
				{card.sentence.fr}
			</p>
		{/if}
	</div>

	<div class="grid gap-2.5">
		{#each card.options ?? [] as option, i (option)}
			<button
				class="flex items-center gap-3.5 rounded-2xl px-4 py-3.5 text-left text-[1.0625rem] text-ink-200 ring-1 ring-inset transition duration-200 active:scale-[0.99] {optionClass(option)}"
				onclick={() => choose(option)}
				disabled={picked !== null}
			>
				<kbd
					class="grid h-6 w-6 shrink-0 place-items-center rounded-md bg-ink-800 text-xs text-ink-400 tabular"
					>{i + 1}</kbd
				>
				<span>{option}</span>
			</button>
		{/each}
	</div>
</div>
