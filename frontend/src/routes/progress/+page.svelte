<script lang="ts">
	import { api, type ActivityDay, type GrowthResponse, type WordProgress } from '$lib/api';
	import ActivityCalendar from '$lib/components/ActivityCalendar.svelte';
	import ArticleWord from '$lib/components/ArticleWord.svelte';
	import GrowthChart from '$lib/components/GrowthChart.svelte';

	let growth = $state<GrowthResponse | null>(null);
	let words = $state<WordProgress[]>([]);
	let activity = $state<ActivityDay[]>([]);
	let loading = $state(true);
	let error = $state<string | null>(null);
	let filter = $state<'all' | 'mastered' | 'learning' | 'new'>('learning');
	let query = $state('');
	let limit = $state(60);

	async function load() {
		loading = true;
		error = null;
		try {
			const [g, w, a] = await Promise.all([api.getGrowth(), api.getWords(), api.getActivity()]);
			growth = g;
			words = w;
			activity = a.days;
			if (!w.some((x) => !x.mastered && (x.recognition_mastery > 0 || x.production_mastery > 0))) filter = 'all';
		} catch (e) {
			error = (e as Error).message;
		} finally {
			loading = false;
		}
	}

	load();

	const counts = $derived({
		mastered: words.filter((w) => w.mastered).length,
		learning: words.filter((w) => !w.mastered && (w.recognition_mastery > 0 || w.production_mastery > 0)).length
	});

	const filtered = $derived.by(() => {
		const q = query.trim().toLowerCase();
		return words.filter((w) => {
			if (q && !w.lemma.toLowerCase().includes(q) && !w.translation_en.toLowerCase().includes(q)) return false;
			if (filter === 'mastered') return w.mastered;
			if (filter === 'new') return w.recognition_mastery === 0 && w.production_mastery === 0;
			if (filter === 'learning') return !w.mastered && (w.recognition_mastery > 0 || w.production_mastery > 0);
			return true;
		});
	});

	const filters = [
		['learning', 'Learning'],
		['mastered', 'Mastered'],
		['new', 'Not started'],
		['all', 'All']
	] as const;
</script>

<svelte:head>
	<title>Progress — 1000 Mots</title>
</svelte:head>

<h1 class="word text-4xl">Progress</h1>

{#if loading}
	<div class="mt-6 space-y-3" aria-busy="true">
		<div class="skeleton h-36"></div>
		<div class="skeleton h-44"></div>
		<div class="skeleton h-64"></div>
	</div>
{:else if error}
	<p class="mt-6 text-bad">{error}</p>
{:else if growth}
	<div class="mt-6 space-y-3 animate-enter">
		<section class="surface grid grid-cols-[1.4fr_1fr] divide-x divide-ink-800 overflow-hidden">
			<div class="p-5">
				<p class="label">Vocabulary known</p>
				<p class="mt-1 text-4xl font-semibold tracking-tight tabular">
					{counts.mastered}<span class="text-lg font-normal text-ink-500"> / {growth.total_words_in_deck.toLocaleString()}</span>
				</p>
				<div class="mt-3 h-1.5 overflow-hidden rounded-full bg-ink-800">
					<div class="h-full rounded-full bg-paper" style:width="{Math.max(growth.coverage_percent, counts.mastered ? 1 : 0)}%"></div>
				</div>
				<p class="mt-2 text-xs text-ink-500 tabular">{growth.coverage_percent}% · {counts.learning} in progress</p>
			</div>
			<div class="p-5">
				<p class="label">Streak</p>
				<p class="mt-1 text-4xl font-semibold tracking-tight tabular">
					{growth.current_streak}<span class="text-lg font-normal text-ink-500"> d</span>
				</p>
				<p class="mt-5 text-xs text-ink-500 tabular">best {growth.longest_streak} day{growth.longest_streak === 1 ? '' : 's'}</p>
			</div>
		</section>

		<section class="surface p-5">
			<p class="label mb-4">Review activity</p>
			<ActivityCalendar days={activity} />
		</section>

		<section class="surface p-5">
			<p class="label mb-2">Words mastered over time</p>
			{#if growth.points.length > 0}
				<GrowthChart points={growth.points} />
			{:else}
				<p class="py-10 text-center text-sm text-ink-500">
					A word counts as mastered once you both recognize and produce it reliably. Your first one starts this chart.
				</p>
			{/if}
		</section>

		<section class="pt-5">
			<h2 class="word text-2xl">Words</h2>
			<input
				bind:value={query}
				type="search"
				placeholder="Search French or English…"
				class="field mt-3 text-base"
				oninput={() => (limit = 60)}
			/>
			<div class="mt-3 flex gap-1.5 overflow-x-auto pb-1">
				{#each filters as [key, label] (key)}
					<button
						onclick={() => {
							filter = key;
							limit = 60;
						}}
						class="chip whitespace-nowrap {filter === key
							? 'bg-paper text-ink-950'
							: 'bg-ink-900 text-ink-400 ring-1 ring-inset ring-ink-800 hover:text-ink-200'}"
					>
						{label}
					</button>
				{/each}
			</div>

			<ul class="surface mt-3 divide-y divide-ink-800 overflow-hidden">
				{#each filtered.slice(0, limit) as w (w.id)}
					<li>
						<a href="/words/{w.id}" class="flex items-center gap-3 px-4 py-3 transition-colors hover:bg-ink-850">
							<span class="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-ink-850 text-lg" aria-hidden="true">
								{#if w.emoji}{w.emoji}{:else}<span class="font-serif text-sm text-ink-600">{w.lemma[0]}</span>{/if}
							</span>
							<span class="min-w-0 flex-1">
								<span class="word block truncate text-lg leading-tight">
									<ArticleWord text={w.display_lemma} lemma={w.lemma} gender={w.gender} />
								</span>
								<span class="block truncate text-sm text-ink-500">{w.translation_en}</span>
							</span>
							{#if w.mastered}
								<span class="rounded-md bg-good/15 px-2 py-0.5 text-xs font-medium text-good">Mastered</span>
							{:else}
								<span class="flex gap-3 text-xs text-ink-500 tabular" title="Recognition / production mastery (0–5)">
									{#each [['R', w.recognition_mastery], ['P', w.production_mastery]] as [k, v] (k)}
										<span class="flex items-center gap-1.5">
											{k}
											<span class="flex gap-[2px]">
												{#each [1, 2, 3, 4, 5] as n (n)}
													<span class="h-2.5 w-1 rounded-full {Number(v) >= n ? 'bg-paper' : 'bg-ink-700'}"></span>
												{/each}
											</span>
										</span>
									{/each}
								</span>
							{/if}
						</a>
					</li>
				{/each}
				{#if filtered.length === 0}
					<li class="px-4 py-8 text-center text-sm text-ink-500">
						{query ? `No words match “${query}”.` : 'No words here yet.'}
					</li>
				{/if}
			</ul>
			{#if filtered.length > limit}
				<button onclick={() => (limit += 120)} class="btn-quiet mt-3 w-full text-sm">
					Show more · {(filtered.length - limit).toLocaleString()} left
				</button>
			{/if}
		</section>
	</div>
{/if}
