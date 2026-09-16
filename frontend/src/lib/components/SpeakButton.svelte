<script lang="ts">
	import { speak, speechSupported } from '$lib/speech';

	let {
		text,
		slow = false,
		label = 'Play pronunciation',
		size = 'md'
	}: { text: string; slow?: boolean; label?: string; size?: 'sm' | 'md' | 'lg' } = $props();
</script>

{#if speechSupported}
	<button
		type="button"
		onclick={() => speak(text, { slow })}
		aria-label={label}
		title={label}
		class="inline-grid shrink-0 place-items-center rounded-full bg-ink-800 text-ink-300 transition duration-200 hover:bg-ink-700 hover:text-ink-100 active:scale-95"
		class:h-9={size === 'sm'}
		class:w-9={size === 'sm'}
		class:h-11={size === 'md'}
		class:w-11={size === 'md'}
		class:h-16={size === 'lg'}
		class:w-16={size === 'lg'}
	>
		<svg
			viewBox="0 0 24 24"
			fill="none"
			stroke="currentColor"
			stroke-width="1.75"
			stroke-linecap="round"
			stroke-linejoin="round"
			class={size === 'lg' ? 'h-6 w-6' : 'h-4 w-4'}
			aria-hidden="true"
		>
			<path d="M11 5 6 9H3v6h3l5 4V5Z" />
			{#if slow}
				<path d="M15.5 12h.01" />
			{:else}
				<path d="M15.5 8.5a5 5 0 0 1 0 7M18.5 5.5a9 9 0 0 1 0 13" />
			{/if}
		</svg>
	</button>
{/if}
