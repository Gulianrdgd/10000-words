<script lang="ts">
	// Mode 6: hear the French, choose the English. Same options as the written
	// MCQ, but the word itself is never shown — so it tests the sound, not the
	// spelling. Only served after a word's first written exposure.
	import type { DueCard } from '$lib/api';
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

	// Respects "Play words automatically": with it off the big play button is
	// the prompt, rather than the app speaking the moment a card appears.
	$effect(() => {
		if (!settings.autoplayAudio) return;
		const t = setTimeout(() => speak(card.display_lemma), 150);
		return () => clearTimeout(t);
	});

	function choose(option: string) {
		if (picked !== null) return;
		picked = option;
		onAnswer({
			correct: option === card.translation_en,
			latencyMs: Date.now() - shownAt,
			picked: option
		});
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

<div class="space-y-9">
	<div class="space-y-6">
		<PromptLabel text="What did you hear?" pos={card.pos} />
		<div class="flex flex-col items-center gap-4">
			<button
				type="button"
				onclick={() => speak(card.display_lemma)}
				aria-label="Play again"
				class="inline-grid h-20 w-20 place-items-center rounded-full bg-ink-800 text-ink-200 transition duration-200 hover:bg-ink-700 hover:text-ink-100 active:scale-95"
			>
				<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" class="h-7 w-7" aria-hidden="true">
					<path d="M11 5 6 9H3v6h3l5 4V5Z" />
					<path d="M15.5 8.5a5 5 0 0 1 0 7M18.5 5.5a9 9 0 0 1 0 13" />
				</svg>
			</button>
			<button
				type="button"
				onclick={() => speak(card.display_lemma, { slow: true })}
				class="btn-quiet px-3 py-1.5 text-sm"
			>
				Play slowly
			</button>
		</div>
	</div>

	<div class="grid gap-2.5">
		{#each card.options ?? [] as option, i (option)}
			<button
				class="flex items-center gap-3.5 rounded-2xl px-4 py-3.5 text-left text-[1.0625rem] text-ink-200 ring-1 ring-inset transition duration-200 active:scale-[0.99] {optionClass(option)}"
				onclick={() => choose(option)}
				disabled={picked !== null}
			>
				<kbd class="grid h-6 w-6 shrink-0 place-items-center rounded-md bg-ink-800 text-xs text-ink-400 tabular">
					{i + 1}
				</kbd>
				<span>{option}</span>
			</button>
		{/each}
	</div>
</div>
