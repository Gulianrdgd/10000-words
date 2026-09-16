<script lang="ts">
	import { goto } from '$app/navigation';
	import { api, setToken } from '$lib/api';
	import { clearOfflineData } from '$lib/offline.svelte';

	let mode = $state<'login' | 'register'>('login');
	let username = $state('');
	let password = $state('');
	let error = $state<string | null>(null);
	let busy = $state(false);

	// a few picturable words drifting behind the form, gender-tinted like in the app
	const specimens = [
		{ art: 'la', word: 'maison', emoji: '🏠', g: 'f' },
		{ art: 'le', word: 'chat', emoji: '🐈', g: 'm' },
		{ art: 'la', word: 'lune', emoji: '🌙', g: 'f' },
		{ art: 'le', word: 'pain', emoji: '🍞', g: 'm' }
	];

	async function submit(e: SubmitEvent) {
		e.preventDefault();
		busy = true;
		error = null;
		try {
			const res =
				mode === 'login' ? await api.login(username, password) : await api.register(username, password);
			// a queued review or cached session could belong to a different account
			clearOfflineData();
			setToken(res.token);
			goto('/');
		} catch (err) {
			error = (err as Error).message;
		} finally {
			busy = false;
		}
	}
</script>

<svelte:head>
	<title>Sign in — 1000 Mots</title>
</svelte:head>

<div class="flex min-h-[90dvh] flex-col justify-center py-10">
	<ul class="mb-10 grid grid-cols-2 gap-2.5" aria-hidden="true">
		{#each specimens as s, i (s.word)}
			<li
				class="surface flex animate-enter items-center gap-3 px-4 py-3"
				style:animation-delay="{i * 70}ms"
			>
				<span class="text-2xl">{s.emoji}</span>
				<span class="word text-xl">
					<span class="font-normal italic {s.g === 'm' ? 'text-masc' : 'text-fem'}">{s.art}</span>
					{s.word}
				</span>
			</li>
		{/each}
	</ul>

	<h1 class="word text-5xl leading-none">1000 Mots</h1>
	<p class="mt-3 max-w-[34ch] text-ink-400">
		The 10,000 most useful French words, one short daily session at a time.
	</p>

	<div class="mt-8 grid grid-cols-2 rounded-xl bg-ink-900 p-1 ring-1 ring-inset ring-ink-800" role="tablist">
		{#each [['login', 'Sign in'], ['register', 'Create account']] as [key, label] (key)}
			<button
				role="tab"
				aria-selected={mode === key}
				onclick={() => {
					mode = key as typeof mode;
					error = null;
				}}
				class="rounded-lg py-2 text-sm font-medium transition duration-200 {mode === key
					? 'bg-ink-800 text-ink-100'
					: 'text-ink-500 hover:text-ink-300'}"
			>
				{label}
			</button>
		{/each}
	</div>

	<form class="mt-4 space-y-3" onsubmit={submit}>
		<label class="block">
			<span class="label">Username</span>
			<input
				bind:value={username}
				autocomplete="username"
				autocapitalize="off"
				spellcheck="false"
				required
				minlength="2"
				class="field mt-1.5 text-base"
			/>
		</label>
		<label class="block">
			<span class="label">Password</span>
			<input
				bind:value={password}
				type="password"
				autocomplete={mode === 'login' ? 'current-password' : 'new-password'}
				required
				minlength="6"
				class="field mt-1.5 text-base"
			/>
		</label>
		{#if error}
			<p class="text-sm text-bad" role="alert">{error}</p>
		{/if}
		<button type="submit" disabled={busy} class="btn-primary !mt-5 w-full">
			{busy ? 'One moment…' : mode === 'login' ? 'Sign in' : 'Create account'}
		</button>
		{#if mode === 'register'}
			<p class="text-center text-xs text-ink-500">Your progress syncs to every device you sign in on.</p>
		{/if}
	</form>
</div>
