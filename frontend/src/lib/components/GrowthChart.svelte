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
						borderColor: '#f1e6cf',
						backgroundColor: 'rgba(241,230,207,0.08)',
						fill: true,
						tension: 0.3,
						pointRadius: 0,
						borderWidth: 2
					}
				]
			},
			options: {
				responsive: true,
				maintainAspectRatio: false,
				plugins: { legend: { display: false } },
				scales: {
					x: { ticks: { color: '#716b61', maxTicksLimit: 6 }, grid: { display: false }, border: { color: '#34312c' } },
					y: {
						beginAtZero: true,
						ticks: { color: '#716b61', precision: 0 },
						grid: { color: '#25231f' },
						border: { display: false }
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
