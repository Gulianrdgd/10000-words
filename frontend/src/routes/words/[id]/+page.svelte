<script lang="ts">
	import { page } from '$app/stores';
	import { api, type WordDetail } from '$lib/api';
	import SpeakButton from '$lib/components/SpeakButton.svelte';
	import WordHero from '$lib/components/WordHero.svelte';

	let word = $state<WordDetail | null>(null);
	let error = $state<string | null>(null);

	$effect(() => {
		const id = $page.params.id ?? '';
		word = null;
		api.getWord(id).then(
			(w) => (word = w),
			(e) => (error = (e as Error).message)
		);
	});

	const MODE_LABELS: Record<number, string> = {
		1: 'Multiple choice',
		2: 'Typed recall',
		3: 'Sentence cloze',
		4: 'Free production',
		5: 'Dictation'
	};

	const GENDER_LABELS: Record<string, string> = {
		m: 'masculine',
		f: 'feminine',
		mf: 'masculine or feminine',
		mp: 'masculine plural',
		fp: 'feminine plural'
	};

	const genderStats = $derived.by(() => {
		const graded = word?.reviews.filter((r) => r.gender_correct !== null) ?? [];
		return { total: graded.length, right: graded.filter((r) => r.gender_correct).length };
	});

	function formatDate(iso: string | null) {
		if (!iso) return '—';
		return new Date(iso).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' });
	}
</script>

<svelte:head>
	<title>{word ? `${word.lemma} — 1000 Mots` : 'Word — 1000 Mots'}</title>
</svelte:head>

<a href="/progress" class="inline-flex items-center gap-1.5 text-sm text-ink-500 transition-colors hover:text-ink-200">
	<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" class="h-4 w-4" aria-hidden="true"><path d="M15 18l-6-6 6-6" /></svg>
	Progress
</a>

{#if error}
	<p class="mt-6 text-bad">{error}</p>
{:else if !word}
	<div class="mt-8 flex flex-col items-center gap-4" aria-busy="true">
		<div class="skeleton h-28 w-28 rounded-[1.75rem]"></div>
		<div class="skeleton h-11 w-52"></div>
		<div class="skeleton mt-6 h-24 w-full"></div>
	</div>
{:else}
	<div class="mt-6 space-y-3 pb-8 animate-enter">
		<header class="pb-5">
			<WordHero lemma={word.lemma} displayLemma={word.display_lemma} gender={word.gender} emoji={word.emoji} />
			<p class="mt-2 text-center text-lg text-ink-300">{word.translation_en}</p>
			<p class="mt-3 flex flex-wrap justify-center gap-1.5 text-xs">
				{#each [word.pos, word.gender ? GENDER_LABELS[word.gender] : null, word.cefr_estimate, `#${word.frequency_rank} most frequent`].filter(Boolean) as tag (tag)}
					<span
						class="rounded-md bg-ink-900 px-2 py-1 ring-1 ring-inset ring-ink-800 {tag === GENDER_LABELS[word.gender ?? '']
							? word.gender?.startsWith('m') && word.gender !== 'mf'
								? 'text-masc'
								: word.gender?.startsWith('f')
									? 'text-fem'
									: 'text-ink-400'
							: 'text-ink-400'}">{tag}</span
					>
				{/each}
			</p>
		</header>

		{#if word.sentences.length > 0}
			<section class="space-y-2">
				{#each word.sentences as s (s.fr)}
					<figure class="surface flex items-start gap-3 p-4">
						<div class="flex-1">
							<p class="font-serif text-lg leading-snug text-ink-100">{s.fr}</p>
							<p class="mt-1 text-sm text-ink-400">{s.en}</p>
						</div>
						<SpeakButton text={s.fr} size="sm" label="Play sentence" />
					</figure>
				{/each}
			</section>
		{/if}

		<section class="grid grid-cols-2 gap-2.5">
			{#each word.tracks as t (t.track)}
				<div class="surface p-4">
					<p class="label capitalize">{t.track}</p>
					<div class="mt-2 flex gap-1" aria-label="{t.mastery_level} of 5">
						{#each [1, 2, 3, 4, 5] as n (n)}
							<span class="h-1.5 flex-1 rounded-full {t.mastery_level >= n ? 'bg-paper' : 'bg-ink-800'}"></span>
						{/each}
					</div>
					<p class="mt-3 text-xs leading-relaxed text-ink-500 tabular">
						{#if t.introduced}
							{t.reps} review{t.reps === 1 ? '' : 's'} · {t.lapses} lapse{t.lapses === 1 ? '' : 's'}<br />next {formatDate(t.due_date)}
						{:else}
							not started
						{/if}
					</p>
				</div>
			{/each}
		</section>

		{#if word.mastered_at || genderStats.total > 0}
			<section class="surface divide-y divide-ink-800 text-sm">
				{#if word.mastered_at}
					<p class="flex justify-between px-4 py-3"><span class="text-ink-400">Mastered</span><span class="tabular">{formatDate(word.mastered_at)}</span></p>
				{/if}
				{#if genderStats.total > 0}
					<p class="flex justify-between px-4 py-3">
						<span class="text-ink-400">Gender right</span><span class="tabular">{genderStats.right} of {genderStats.total}</span>
					</p>
				{/if}
			</section>
		{/if}

		<section class="pt-4">
			<h2 class="word text-2xl">History</h2>
			{#if word.reviews.length === 0}
				<p class="mt-2 text-sm text-ink-500">No reviews yet — this word shows up once it's introduced.</p>
			{:else}
				<ol class="mt-3 space-y-0">
					{#each word.reviews as r, i (i)}
						<li class="relative flex items-center gap-3 py-2 pl-6 text-sm">
							<span class="absolute left-[5px] top-0 w-px bg-ink-800 {i === word.reviews.length - 1 ? 'h-1/2' : 'h-full'}"></span>
							<span
								class="absolute left-0 h-[11px] w-[11px] rounded-full ring-2 ring-ink-950 {r.correct ? 'bg-good' : 'bg-bad'}"
							></span>
							<span class="flex-1 text-ink-200">{MODE_LABELS[r.mode] ?? `Mode ${r.mode}`}</span>
							<span class="text-xs {r.correct ? 'text-good' : 'text-bad'}">
								{#if r.correct}
									{r.near_miss ? 'close' : 'correct'}
								{:else if r.gender_correct === false}
									wrong gender
								{:else}
									missed
								{/if}
							</span>
							<span class="w-20 text-right text-xs text-ink-500 tabular">{formatDate(r.timestamp)}</span>
						</li>
					{/each}
				</ol>
			{/if}
		</section>
	</div>
{/if}
