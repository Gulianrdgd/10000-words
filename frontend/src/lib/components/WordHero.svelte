<script lang="ts">
	import type { Gender } from '$lib/api';
	import ArticleWord from '$lib/components/ArticleWord.svelte';
	import SpeakButton from '$lib/components/SpeakButton.svelte';

	let {
		lemma,
		displayLemma,
		gender,
		emoji = null,
		size = 'lg',
		speak = true
	}: {
		lemma: string;
		displayLemma: string;
		gender: Gender;
		emoji?: string | null;
		size?: 'lg' | 'md';
		speak?: boolean;
	} = $props();
</script>

<div class="flex flex-col items-center text-center">
	{#if emoji}
		<div
			class="grid place-items-center rounded-[1.75rem] bg-ink-900 ring-1 ring-inset ring-ink-800"
			class:h-28={size === 'lg'}
			class:w-28={size === 'lg'}
			class:text-6xl={size === 'lg'}
			class:h-20={size === 'md'}
			class:w-20={size === 'md'}
			class:text-4xl={size === 'md'}
			aria-hidden="true"
		>
			<span class="leading-none">{emoji}</span>
		</div>
	{/if}
	<div class="flex items-center gap-3" class:mt-5={!!emoji}>
		<h2
			class="word leading-[1.05]"
			class:text-5xl={size === 'lg'}
			class:text-4xl={size === 'md'}
		>
			<ArticleWord text={displayLemma} {lemma} {gender} />
		</h2>
		{#if speak}
			<SpeakButton text={displayLemma} size="sm" />
		{/if}
	</div>
</div>
