<script lang="ts">
	import type { DueCard } from '$lib/api';

	let {
		card,
		onAnswer
	}: {
		card: DueCard;
		onAnswer: (result: { selfReportedCorrect: boolean; latencyMs: number }) => void;
	} = $props();

	let draft = $state('');
	let revealed = $state(false);
	let shownAt = $state(Date.now());

	$effect(() => {
		card.card_id;
		draft = '';
		revealed = false;
		shownAt = Date.now();
	});

	function reveal() {
		revealed = true;
	}

	function report(selfReportedCorrect: boolean) {
		onAnswer({ selfReportedCorrect, latencyMs: Date.now() - shownAt });
	}
</script>

<div class="space-y-6">
	<div class="text-center">
		<p class="text-xs uppercase tracking-wide text-slate-500">{card.pos} · free production</p>
		<h2 class="mt-2 text-3xl font-semibold text-slate-50">{card.lemma}</h2>
		<p class="mt-1 text-sm text-slate-400">{card.translation_en}</p>
		<p class="mt-4 text-base text-slate-300">Use this word in your own French sentence.</p>
	</div>

	<textarea
		bind:value={draft}
		rows="2"
		placeholder="Écris ta propre phrase… (optional, just for you)"
		class="w-full resize-none rounded-lg border border-slate-700 bg-slate-900 px-4 py-3 text-base text-slate-50 placeholder-slate-600 focus:border-brand-400 focus:outline-none"
	></textarea>

	{#if !revealed}
		<button
			onclick={reveal}
			class="w-full rounded-lg bg-brand-500 py-3 text-base font-medium text-white"
		>
			Show a model sentence
		</button>
	{:else}
		{#if card.sentence}
			<div class="rounded-lg border border-slate-800 bg-slate-900 p-4">
				<p class="text-base text-slate-100">{card.sentence.fr}</p>
				<p class="mt-1 text-sm text-slate-400">{card.sentence.en}</p>
			</div>
		{/if}
		<p class="text-center text-sm text-slate-400">Was your sentence correct?</p>
		<div class="grid grid-cols-2 gap-3">
			<button
				onclick={() => report(false)}
				class="rounded-lg border border-rose-500/60 bg-rose-500/10 py-3 font-medium text-rose-300"
			>
				Needs work
			</button>
			<button
				onclick={() => report(true)}
				class="rounded-lg border border-emerald-500/60 bg-emerald-500/10 py-3 font-medium text-emerald-300"
			>
				Got it right
			</button>
		</div>
	{/if}
</div>
