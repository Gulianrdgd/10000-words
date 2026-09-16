<script lang="ts">
	import type { Gender } from '$lib/api';

	// Renders "la maison" with the article tinted by gender (a memory cue):
	// masculine blue, feminine rose. `text` is any form ending in the lemma.
	let { text, lemma, gender }: { text: string; lemma: string; gender: Gender } = $props();

	const article = $derived(text.endsWith(lemma) ? text.slice(0, text.length - lemma.length) : '');
	const rest = $derived(article ? lemma : text);
	const tint = $derived(
		gender === 'm' || gender === 'mp' ? 'text-masc' : gender === 'f' || gender === 'fp' ? 'text-fem' : 'text-ink-400'
	);
</script>

{#if article}<span class="font-normal italic {tint}">{article}</span>{/if}{rest}
