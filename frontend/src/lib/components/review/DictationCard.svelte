<script lang="ts">
	import type { DueCard } from '$lib/api';
	import SpeakButton from '$lib/components/SpeakButton.svelte';
	import PromptLabel from './PromptLabel.svelte';
	import { isSpeakShortcut, speak } from '$lib/speech';

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
	const audioText = $derived(card.expected_answer ?? card.lemma);

	$effect(() => {
		inputEl?.focus();
		// give the browser a beat to settle focus before speaking
		const t = setTimeout(() => speak(audioText), 150);
		return () => clearTimeout(t);
	});

	function submit() {
		if (answered || !value.trim()) return;
		answered = true;
		onAnswer({ typedAnswer: value.trim(), latencyMs: Date.now() - shownAt });
	}

	function onkeydown(e: KeyboardEvent) {
		if (!answered && isSpeakShortcut(e)) {
			e.preventDefault();
			speak(audioText);
		}
	}
</script>

<svelte:window {onkeydown} />

<div class="space-y-9">
	<div class="space-y-7">
		<PromptLabel text="Type what you hear" pos={card.pos} />
		<div class="flex items-center justify-center gap-4">
			<div class="relative">
				<span class="absolute inset-0 animate-ping rounded-full bg-paper/10 [animation-iteration-count:2]"></span>
				<SpeakButton text={audioText} size="lg" label="Play again" />
			</div>
			<SpeakButton text={audioText} slow label="Play slowly" />
		</div>
		{#if card.pos === 'noun' && (card.gender === 'm' || card.gender === 'f')}
			<p class="text-center text-sm text-ink-500">Include the article you hear.</p>
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
			placeholder="Écris ce que tu entends…"
			class="field font-serif text-xl"
		/>
		<button type="submit" class="btn-primary w-full" disabled={!value.trim() || answered}>
			Check
		</button>
		<p class="text-center text-xs text-ink-600">
			<kbd class="rounded bg-ink-800 px-1.5 py-0.5 text-ink-400">Alt P</kbd> replay
		</p>
	</form>
</div>
