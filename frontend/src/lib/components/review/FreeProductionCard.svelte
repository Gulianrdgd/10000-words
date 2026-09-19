<script lang="ts">
	import type { DueCard } from '$lib/api';
	import SpeakButton from '$lib/components/SpeakButton.svelte';
	import WordHero from '$lib/components/WordHero.svelte';
	import PromptLabel from './PromptLabel.svelte';
	import { isSpeakShortcut, isTypingTarget, speak } from '$lib/speech';

	let {
		card,
		onAnswer
	}: {
		card: DueCard;
		onAnswer: (result: { selfReportedCorrect: boolean; latencyMs: number }) => void;
	} = $props();

	let draft = $state('');
	let revealed = $state(false);
	let reported = $state(false);
	const shownAt = Date.now();

	function reveal() {
		revealed = true;
	}

	function report(selfReportedCorrect: boolean) {
		if (reported) return;
		reported = true;
		onAnswer({ selfReportedCorrect, latencyMs: Date.now() - shownAt });
	}

	function onkeydown(e: KeyboardEvent) {
		if (reported) return;
		if (isSpeakShortcut(e)) {
			e.preventDefault();
			speak(revealed && card.sentence ? card.sentence.fr : card.display_lemma);
			return;
		}
		// Enter reveals (Ctrl/Cmd+Enter from inside the textarea)
		if (!revealed && e.key === 'Enter' && (!isTypingTarget(e.target) || e.metaKey || e.ctrlKey)) {
			e.preventDefault();
			reveal();
			return;
		}
		if (revealed && !isTypingTarget(e.target) && (e.key === '1' || e.key === '2')) {
			e.preventDefault();
			report(e.key === '2');
		}
	}
</script>

<svelte:window {onkeydown} />

<div class="space-y-8">
	<div class="space-y-6">
		<PromptLabel text="Use it in your own sentence" pos={card.pos} />
		<WordHero lemma={card.lemma} displayLemma={card.display_lemma} gender={card.gender} emoji={card.emoji} size="md" />
		<p class="text-center text-ink-400">{card.translation_en}</p>
	</div>

	<textarea
		aria-label="Your own French sentence"
		bind:value={draft}
		rows="3"
		lang="fr"
		placeholder="Écris ta propre phrase… (just for you, not graded)"
		class="field resize-none font-serif text-lg"
	></textarea>

	{#if !revealed}
		<button onclick={reveal} class="btn-primary w-full">Compare with an example</button>
	{:else}
		<div class="animate-enter space-y-4">
			{#if card.sentence}
				<figure class="surface flex items-start gap-3 p-4">
					<div class="flex-1">
						<p class="font-serif text-lg leading-snug text-ink-100">{card.sentence.fr}</p>
						<p class="mt-1 text-sm text-ink-400">{card.sentence.en}</p>
					</div>
					<SpeakButton text={card.sentence.fr} size="sm" label="Play sentence" />
				</figure>
			{/if}
			<p class="label text-center">Was your sentence correct?</p>
			<div class="grid grid-cols-2 gap-2.5">
				<button onclick={() => report(false)} class="btn bg-bad/10 text-bad ring-1 ring-inset ring-bad/40 hover:bg-bad/20">
					Needs work <kbd class="hidden text-xs opacity-60 sm:inline">1</kbd>
				</button>
				<button onclick={() => report(true)} class="btn bg-good/10 text-good ring-1 ring-inset ring-good/40 hover:bg-good/20">
					Got it right <kbd class="hidden text-xs opacity-60 sm:inline">2</kbd>
				</button>
			</div>
		</div>
	{/if}
</div>
