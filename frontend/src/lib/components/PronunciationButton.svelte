<script lang="ts">
	import { pronunciationAvailable, type Assessment } from '$lib/pronunciation';
	import { createRecorder } from '$lib/recorder.svelte';

	let { text }: { text: string } = $props();

	let available = $state(false);
	pronunciationAvailable().then((ok) => (available = ok));

	let result = $state<Assessment | null>(null);
	const recorder = createRecorder((assessment) => (result = assessment));
	$effect(() => recorder.dispose);

	function tone(score: number) {
		return score >= 80 ? 'text-good' : score >= 60 ? 'text-ink-200' : 'text-bad';
	}
</script>

{#if available}
	<section class="surface p-5">
		<div class="flex items-center justify-between gap-4">
			<div>
				<h2 class="text-[0.9375rem] font-medium">Say it</h2>
				<p class="mt-1 text-sm text-ink-500">
					{recorder.recording
						? 'Recording — say the word, then press again to stop.'
						: recorder.scoring
							? 'Scoring…'
							: 'Record yourself and get a pronunciation score.'}
				</p>
			</div>
			<button
				type="button"
				onclick={() => recorder.toggle(text)}
				disabled={recorder.scoring}
				aria-pressed={recorder.recording}
				aria-label="Record your pronunciation"
				class="inline-grid h-11 w-11 shrink-0 place-items-center rounded-full transition duration-200 active:scale-95 {recorder.recording
					? 'animate-pulse bg-bad text-paper'
					: 'bg-ink-800 text-ink-300 hover:bg-ink-700 hover:text-ink-100'}"
			>
				<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" class="h-4 w-4" aria-hidden="true">
					<rect x="9" y="2" width="6" height="11" rx="3" />
					<path d="M5 11a7 7 0 0 0 14 0M12 18v4" />
				</svg>
			</button>
		</div>

		{#if recorder.error}
			<p class="mt-4 text-sm text-bad" role="status">{recorder.error}</p>
		{/if}

		{#if result}
			<div class="mt-5" role="status">
				<div class="flex items-baseline gap-2">
					<span class="text-4xl font-semibold tabular {tone(result.pronunciation)}">{result.pronunciation}</span>
					<span class="text-sm text-ink-500">/ 100</span>
				</div>
				<dl class="mt-3 grid grid-cols-3 gap-2 text-center">
					{#each [['Accuracy', result.accuracy], ['Fluency', result.fluency], ['Complete', result.completeness]] as [name, score] (name)}
						<div class="rounded-lg bg-ink-950 py-2 ring-1 ring-inset ring-ink-800">
							<dt class="label">{name}</dt>
							<dd class="mt-0.5 text-lg tabular {tone(score as number)}">{score}</dd>
						</div>
					{/each}
				</dl>

				<ul class="mt-4 space-y-2">
					{#each result.words as w (w.word)}
						<li>
							<p class="flex items-baseline justify-between gap-3">
								<span class="font-serif text-lg {tone(w.accuracy)}">{w.word}</span>
								<span class="text-xs text-ink-500 tabular">
									{w.errorType !== 'None' ? w.errorType.toLowerCase() : w.accuracy}
								</span>
							</p>
							{#if w.phonemes.length > 0}
								<p class="mt-1 flex flex-wrap gap-1">
									{#each w.phonemes as p, i (i)}
										<span class="rounded bg-ink-900 px-1.5 py-0.5 text-xs ring-1 ring-inset ring-ink-800 {tone(p.accuracy)}">
											{p.phoneme}
										</span>
									{/each}
								</p>
							{/if}
						</li>
					{/each}
				</ul>
				<p class="mt-3 text-xs text-ink-500">Practice only — this doesn't change your review schedule.</p>
			</div>
		{/if}
	</section>
{/if}
