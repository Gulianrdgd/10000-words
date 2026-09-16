<script lang="ts">
	import type { ActivityDay } from '$lib/api';

	let { days, weeks = 20 }: { days: ActivityDay[]; weeks?: number } = $props();

	function localISO(d: Date) {
		return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
	}

	// Columns of Monday→Sunday, ending with the current week.
	const grid = $derived.by(() => {
		const byDate = new Map(days.map((d) => [d.date, d]));
		const today = new Date();
		const start = new Date(today);
		start.setDate(today.getDate() - ((today.getDay() + 6) % 7) - (weeks - 1) * 7);
		const todayISO = localISO(today);
		return Array.from({ length: weeks }, (_, w) =>
			Array.from({ length: 7 }, (_, d) => {
				const date = new Date(start);
				date.setDate(start.getDate() + w * 7 + d);
				const iso = localISO(date);
				return { iso, future: iso > todayISO, today: iso === todayISO, reviews: byDate.get(iso)?.reviews ?? 0 };
			})
		);
	});

	const activeDays = $derived(days.length);
	const totalReviews = $derived(days.reduce((sum, d) => sum + d.reviews, 0));

	// one hue (the accent), stepped by opacity
	function shade(reviews: number) {
		if (reviews === 0) return 'bg-ink-800';
		if (reviews < 10) return 'bg-paper/25';
		if (reviews < 30) return 'bg-paper/50';
		if (reviews < 60) return 'bg-paper/75';
		return 'bg-paper';
	}
</script>

<div>
	<div class="flex gap-[3px]">
		{#each grid as week, w (w)}
			<div class="flex flex-1 flex-col gap-[3px]">
				{#each week as day (day.iso)}
					<div
						class="aspect-square w-full rounded-[3px] {day.future ? 'bg-transparent' : shade(day.reviews)}"
						class:ring-1={day.today}
						class:ring-ink-400={day.today}
						title={day.future ? '' : `${day.iso}: ${day.reviews} review${day.reviews === 1 ? '' : 's'}`}
					></div>
				{/each}
			</div>
		{/each}
	</div>
	<div class="mt-3 flex items-center justify-between text-xs text-ink-500 tabular">
		<span>{totalReviews} reviews · {activeDays} active day{activeDays === 1 ? '' : 's'}</span>
		<span class="flex items-center gap-1">
			less
			{#each ['bg-ink-800', 'bg-paper/25', 'bg-paper/50', 'bg-paper/75', 'bg-paper'] as c (c)}
				<span class="h-2.5 w-2.5 rounded-[2px] {c}"></span>
			{/each}
			more
		</span>
	</div>
</div>
