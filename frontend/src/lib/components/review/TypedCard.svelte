<script lang="ts">
	import type { DueCard } from '$lib/api';

	let {
		card,
		onAnswer
	}: {
		card: DueCard;
		onAnswer: (result: { typedAnswer: string; latencyMs: number }) => void;
	} = $props();

	let value = $state('');
	let shownAt = $state(Date.now());
	let inputEl: HTMLInputElement | undefined = $state();

	$effect(() => {
		card.card_id;
		value = '';
		shownAt = Date.now();
		inputEl?.focus();
	});

	function submit() {
		if (!value.trim()) return;
		onAnswer({ typedAnswer: value.trim(), latencyMs: Date.now() - shownAt });
	}
</script>

<div class="space-y-6">
	<div class="text-center">
		<p class="text-xs uppercase tracking-wide text-slate-500">
			{card.pos} · {card.mode === 3 ? 'complete the sentence' : 'type the French word'}
		</p>

		{#if card.mode === 3 && card.cloze_sentence}
			<h2 class="mt-2 text-2xl font-semibold leading-snug text-slate-50">{card.cloze_sentence}</h2>
			{#if card.sentence}
				<p class="mt-3 text-sm italic text-slate-400">{card.sentence.en}</p>
			{/if}
		{:else}
			<h2 class="mt-2 text-3xl font-semibold text-slate-50">{card.translation_en}</h2>
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
			type="text"
			autocomplete="off"
			autocapitalize="off"
			spellcheck="false"
			placeholder="Écris le mot en français…"
			class="w-full rounded-xl border border-slate-700 bg-slate-900 px-4 py-3 text-lg text-slate-50 placeholder-slate-600 focus:border-brand-400 focus:outline-none"
		/>
		<button
			type="submit"
			class="w-full rounded-xl bg-brand-500 py-3 text-base font-medium text-white disabled:opacity-40"
			disabled={!value.trim()}
		>
			Check
		</button>
	</form>
</div>
