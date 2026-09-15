<script lang="ts">
	import type { GrowthPoint } from '$lib/api';
	import {
		Chart,
		LineController,
		LineElement,
		PointElement,
		LinearScale,
		CategoryScale,
		Filler,
		Tooltip
	} from 'chart.js';

	Chart.register(LineController, LineElement, PointElement, LinearScale, CategoryScale, Filler, Tooltip);

	let { points }: { points: GrowthPoint[] } = $props();

	let canvasEl: HTMLCanvasElement | undefined = $state();
	let chart: Chart | undefined;

	function render() {
		if (!canvasEl) return;
		const labels = points.map((p) => p.date.slice(5));
		const data = points.map((p) => p.cumulative_mastered);

		if (chart) {
			chart.data.labels = labels;
			chart.data.datasets[0].data = data;
			chart.update();
			return;
		}

		chart = new Chart(canvasEl, {
			type: 'line',
			data: {
				labels,
				datasets: [
					{
						label: 'Words mastered',
						data,
						borderColor: '#5588f5',
						backgroundColor: 'rgba(85,136,245,0.15)',
						fill: true,
						tension: 0.3,
						pointRadius: 2
					}
				]
			},
			options: {
				responsive: true,
				maintainAspectRatio: false,
				plugins: { legend: { display: false } },
				scales: {
					x: { ticks: { color: '#64748b' }, grid: { color: '#1e293b' } },
					y: {
						beginAtZero: true,
						ticks: { color: '#64748b', precision: 0 },
						grid: { color: '#1e293b' }
					}
				}
			}
		});
	}

	$effect(() => {
		points;
		render();
	});
</script>

<div class="h-56 w-full">
	<canvas bind:this={canvasEl}></canvas>
</div>
