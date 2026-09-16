<script lang="ts">
	import { goto } from '$app/navigation';
	import { api, setToken } from '$lib/api';
	import { clearOfflineData, sync } from '$lib/offline.svelte';
	import { saveSettings, settings } from '$lib/settings.svelte';
	import { speak, speechSupported } from '$lib/speech';

	const SESSION_SIZES = [10, 20, 30, 50];

	let username = $state<string | null>(null);
	api.me().then((me) => (username = me.username), () => {});

	// --- reminders ---------------------------------------------------------------
	const pushSupported =
		typeof window !== 'undefined' &&
		'serviceWorker' in navigator &&
		'PushManager' in window &&
		'Notification' in window;

	let subscription = $state<PushSubscription | null>(null);
	let reminderHour = $state(18);
	let pushBusy = $state(false);
	let pushMessage = $state<string | null>(null);

	function registration(): Promise<ServiceWorkerRegistration> {
		return Promise.race([
			navigator.serviceWorker.ready,
			new Promise<never>((_, reject) =>
				setTimeout(() => reject(new Error('Service worker not available — use the installed app / production build')), 4000)
			)
		]);
	}

	async function loadPushState() {
		if (!pushSupported) return;
		try {
			const sub = await (await registration()).pushManager.getSubscription();
			if (!sub) return;
			const status = await api.getPushStatus(sub.endpoint);
			if (status.subscribed) {
				subscription = sub;
				reminderHour = status.reminder_hour ?? reminderHour;
			}
		} catch {
			// no service worker yet: leave reminders off
		}
	}
	loadPushState();

	function urlBase64ToUint8Array(base64: string): Uint8Array<ArrayBuffer> {
		const padded = (base64 + '='.repeat((4 - (base64.length % 4)) % 4)).replace(/-/g, '+').replace(/_/g, '/');
		const raw = atob(padded);
		const bytes = new Uint8Array(new ArrayBuffer(raw.length));
		for (let i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i);
		return bytes;
	}

	async function enableReminders() {
		pushBusy = true;
		pushMessage = null;
		try {
			if ((await Notification.requestPermission()) !== 'granted') {
				pushMessage = 'Notifications are blocked for this site in your browser settings.';
				return;
			}
			const reg = await registration();
			const { public_key } = await api.getPushPublicKey();
			const sub =
				(await reg.pushManager.getSubscription()) ??
				(await reg.pushManager.subscribe({
					userVisibleOnly: true,
					applicationServerKey: urlBase64ToUint8Array(public_key)
				}));
			await saveSubscription(sub);
			pushMessage = `You'll get a reminder after ${formatHour(reminderHour)} on days with cards due.`;
		} catch (e) {
			pushMessage = (e as Error).message;
		} finally {
			pushBusy = false;
		}
	}

	async function saveSubscription(sub: PushSubscription) {
		const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
		await api.subscribePush(sub.toJSON(), timezone, reminderHour);
		subscription = sub;
	}

	async function disableReminders() {
		if (!subscription) return;
		pushBusy = true;
		try {
			await api.unsubscribePush(subscription.endpoint);
			await subscription.unsubscribe();
			subscription = null;
			pushMessage = null;
		} catch (e) {
			pushMessage = (e as Error).message;
		} finally {
			pushBusy = false;
		}
	}

	async function sendTest() {
		if (!subscription) return;
		try {
			await api.testPush(subscription.endpoint);
			pushMessage = 'Test notification sent.';
		} catch (e) {
			pushMessage = (e as Error).message;
		}
	}

	function formatHour(h: number) {
		return `${String(h).padStart(2, '0')}:00`;
	}

	async function signOut() {
		if (sync.pending > 0 && !confirm(`${sync.pending} offline reviews haven't synced yet and will be lost. Sign out anyway?`)) {
			return;
		}
		await disableReminders();
		await api.logout().catch(() => {});
		clearOfflineData();
		setToken(null);
		goto('/login');
	}
</script>

<svelte:head>
	<title>Settings — 1000 Mots</title>
</svelte:head>

<h1 class="word text-4xl">Settings</h1>

<div class="mt-6 space-y-3 animate-enter">
	<section class="surface p-5">
		<h2 class="text-[0.9375rem] font-medium">Session length</h2>
		<p class="mt-1 text-sm text-ink-500">Cards per session. You can always keep going after one.</p>
		<div class="mt-4 grid grid-cols-4 gap-1 rounded-xl bg-ink-950 p-1 ring-1 ring-inset ring-ink-800">
			{#each SESSION_SIZES as size (size)}
				<button
					onclick={() => {
						settings.sessionSize = size;
						saveSettings();
					}}
					aria-pressed={settings.sessionSize === size}
					class="rounded-lg py-2 text-sm font-medium tabular transition duration-200 {settings.sessionSize === size
						? 'bg-paper text-ink-950'
						: 'text-ink-400 hover:text-ink-100'}"
				>
					{size}
				</button>
			{/each}
		</div>
	</section>

	<section class="surface p-5">
		<h2 class="text-[0.9375rem] font-medium">Audio</h2>
		{#if speechSupported}
			<label class="mt-4 flex cursor-pointer items-center justify-between gap-4">
				<span class="text-sm text-ink-300">Play words automatically</span>
				<input type="checkbox" bind:checked={settings.autoplayAudio} onchange={saveSettings} class="peer sr-only" />
				<span
					class="relative h-6 w-10 shrink-0 rounded-full bg-ink-700 transition peer-checked:bg-paper peer-focus-visible:ring-2 peer-focus-visible:ring-paper/70 after:absolute after:left-1 after:top-1 after:h-4 after:w-4 after:rounded-full after:bg-ink-100 after:transition peer-checked:after:translate-x-4 peer-checked:after:bg-ink-950"
					aria-hidden="true"
				></span>
			</label>
			<div class="mt-5">
				<div class="flex items-center justify-between">
					<span class="text-sm text-ink-300">Speaking speed</span>
					<span class="text-sm text-ink-500 tabular">{settings.speechRate.toFixed(1)}×</span>
				</div>
				<div class="mt-2 flex items-center gap-3">
					<input
						type="range"
						min="0.5"
						max="1.2"
						step="0.1"
						bind:value={settings.speechRate}
						onchange={saveSettings}
						aria-label="Speaking speed"
						class="flex-1 accent-[#f1e6cf]"
					/>
					<button
						onclick={() => speak("Bonjour, je m'appelle Claire. J'habite à Paris.")}
						class="btn-quiet px-3 py-1.5 text-sm"
					>
						Listen
					</button>
				</div>
			</div>
		{:else}
			<p class="mt-1 text-sm text-ink-500">This browser has no speech synthesis, so audio and dictation are off.</p>
		{/if}
	</section>

	<section class="surface p-5">
		<h2 class="text-[0.9375rem] font-medium">Daily reminder</h2>
		{#if !pushSupported}
			<p class="mt-1 text-sm text-ink-500">
				This browser doesn't support push notifications. On iPhone, add the app to your Home Screen first.
			</p>
		{:else}
			<p class="mt-1 text-sm text-ink-500">
				One notification a day, only if you have cards due and haven't reviewed yet.
			</p>
			<label class="mt-4 flex items-center justify-between">
				<span class="text-sm text-ink-300">Remind me after</span>
				<select
					bind:value={reminderHour}
					onchange={() => subscription && saveSubscription(subscription)}
					class="rounded-lg bg-ink-950 px-2.5 py-1.5 text-sm text-ink-100 ring-1 ring-inset ring-ink-700 tabular"
				>
					{#each Array.from({ length: 24 }, (_, h) => h) as h (h)}
						<option value={h}>{formatHour(h)}</option>
					{/each}
				</select>
			</label>
			<div class="mt-4 flex gap-2">
				{#if subscription}
					<button onclick={disableReminders} disabled={pushBusy} class="btn-quiet flex-1 py-2.5 text-sm">
						Turn off
					</button>
					<button onclick={sendTest} class="btn-quiet flex-1 py-2.5 text-sm">Send a test</button>
				{:else}
					<button onclick={enableReminders} disabled={pushBusy} class="btn-primary flex-1 py-2.5 text-sm">
						Turn on reminders
					</button>
				{/if}
			</div>
			{#if pushMessage}
				<p class="mt-3 text-sm text-ink-400" role="status">{pushMessage}</p>
			{/if}
		{/if}
	</section>

	<section class="surface p-5">
		<h2 class="text-[0.9375rem] font-medium">Account</h2>
		<p class="mt-1 text-sm text-ink-500">
			{username ? `Signed in as ${username}. Progress syncs to every device you sign in on.` : 'Signed in.'}
		</p>
		{#if sync.pending > 0}
			<p class="mt-2 text-sm text-bad">{sync.pending} offline review{sync.pending === 1 ? '' : 's'} waiting to sync.</p>
		{/if}
		<button onclick={signOut} class="btn-quiet mt-4 w-full py-2.5 text-sm">Sign out</button>
	</section>

	<section class="px-1 pt-3 text-sm text-ink-500">
		<h2 class="font-medium text-ink-400">Keyboard shortcuts</h2>
		<dl class="mt-2 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5">
			{#each [['1–4', 'pick an answer'], ['Enter', 'check / continue'], ['P', 'play audio (Alt P while typing)']] as [k, v] (k)}
				<dt><kbd class="rounded bg-ink-800 px-1.5 py-0.5 text-xs text-ink-300">{k}</kbd></dt>
				<dd>{v}</dd>
			{/each}
		</dl>
	</section>
</div>
