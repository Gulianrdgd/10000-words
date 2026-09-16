<script lang="ts">
	let { text, pos }: { text: string; pos: string } = $props();
</script>

<p class="label text-center">
	{text}<span class="text-ink-600">{` · ${pos}`}</span>
</p>
