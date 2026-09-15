<script lang="ts">
	import type { ReviewResponse } from '$lib/api';

	let {
		result,
		onContinue
	}: {
		result: ReviewResponse;
		onContinue: () => void;
	} = $props();
</script>

<div
	class="fixed inset-x-0 bottom-16 z-10 border-t px-4 py-4"
	class:border-emerald-500={result.correct}
	class:bg-emerald-950={result.correct}
	class:border-amber-500={!result.correct}
	class:bg-amber-950={!result.correct}
>
	<div class="mx-auto max-w-md space-y-3">
		<div class="flex items-center justify-between">
			<p class="text-base font-semibold" class:text-emerald-300={result.correct} class:text-amber-300={!result.correct}>
				{#if result.correct}
					{result.near_miss ? 'Close enough — correct!' : 'Correct!'}
				{:else}
					Not quite
				{/if}
			</p>
			{#if result.word_mastered}
				<span class="rounded-full bg-brand-500 px-2 py-0.5 text-xs font-medium text-white">
					✨ word mastered
				</span>
			{/if}
		</div>

		{#if !result.correct && result.expected_answer}
			<p class="text-sm text-slate-300">Correct answer: <strong>{result.expected_answer}</strong></p>
		{/if}

		<div class="flex items-center justify-between text-xs text-slate-400">
			<span>Next review in {result.interval_days} day{result.interval_days === 1 ? '' : 's'}</span>
			<span>🔥 {result.streak} day streak</span>
		</div>

		<button
			onclick={onContinue}
			class="w-full rounded-xl bg-slate-100 py-3 text-base font-medium text-slate-950"
		>
			Continue
		</button>
	</div>
</div>
