<script lang="ts">
	import type { DueCard } from '$lib/api';

	let {
		card,
		onAnswer
	}: {
		card: DueCard;
		onAnswer: (result: { correct: boolean; latencyMs: number; picked: string }) => void;
	} = $props();

	let picked = $state<string | null>(null);
	let shownAt = $state(Date.now());

	$effect(() => {
		// re-arm the timer whenever a new card is shown
		card.card_id;
		picked = null;
		shownAt = Date.now();
	});

	function choose(option: string) {
		if (picked !== null) return;
		picked = option;
		const correct = option === card.translation_en;
		onAnswer({ correct, latencyMs: Date.now() - shownAt, picked: option });
	}
</script>

<div class="space-y-6">
	<div class="text-center">
		<p class="text-xs uppercase tracking-wide text-slate-500">{card.pos} · recognize the meaning</p>
		<h2 class="mt-2 text-3xl font-semibold text-slate-50">{card.lemma}</h2>
		{#if card.sentence}
			<p class="mt-3 text-sm italic text-slate-400">{card.sentence.fr}</p>
		{/if}
	</div>

	<div class="grid grid-cols-1 gap-3">
		{#each card.options ?? [] as option (option)}
			{@const isCorrect = option === card.translation_en}
			{@const isPicked = option === picked}
			<button
				class="rounded-lg border px-4 py-3 text-left text-base transition-colors"
				class:border-slate-700={picked === null}
				class:bg-slate-900={picked === null}
				class:hover:border-brand-400={picked === null}
				class:border-emerald-500={picked !== null && isCorrect}
				class:bg-emerald-500={picked !== null && isCorrect}
				class:text-slate-950={picked !== null && isCorrect}
				class:border-rose-500={picked !== null && isPicked && !isCorrect}
				class:bg-rose-500={picked !== null && isPicked && !isCorrect}
				class:opacity-50={picked !== null && !isCorrect && !isPicked}
				onclick={() => choose(option)}
				disabled={picked !== null}
			>
				{option}
			</button>
		{/each}
	</div>
</div>
