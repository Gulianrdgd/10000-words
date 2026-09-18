// French audio. Azure neural voices when the backend has a Speech key — the
// browser's built-in French voices are compact, robotic ones on most machines.
//
// Every clip is cached in the Cache API, keyed by voice + text, so a word costs
// one request ever and then replays instantly and offline. Speed changes are
// applied to playback rather than baked into the request, so the slider and the
// "play slowly" button never re-fetch. Without Azure (or without network on a
// word that was never played), this falls back to speechSynthesis.
import { credentials } from './azure';
import { settings } from './settings.svelte';

const VOICE = 'fr-FR-DeniseNeural';
const CACHE_NAME = 'tts-fr-v1';
const FORMAT = 'audio-24khz-48kbitrate-mono-mp3';

export const speechSupported = typeof window !== 'undefined' && 'speechSynthesis' in window;

// --- Azure neural voice ------------------------------------------------------

const cacheKey = (text: string) => `https://tts.cache/${VOICE}/${encodeURIComponent(text)}`;

const XML_ESCAPES: Record<string, string> = {
	'<': '&lt;',
	'>': '&gt;',
	'&': '&amp;',
	"'": '&apos;',
	'"': '&quot;'
};

function ssml(text: string) {
	const escaped = text.replace(/[<>&'"]/g, (c) => XML_ESCAPES[c]);
	return `<speak version="1.0" xml:lang="fr-FR"><voice name="${VOICE}">${escaped}</voice></speak>`;
}

/** Cache API is missing in insecure contexts and can throw in private mode. */
async function openCache(): Promise<Cache | null> {
	try {
		return typeof caches !== 'undefined' ? await caches.open(CACHE_NAME) : null;
	} catch {
		return null;
	}
}

async function synthesize(text: string): Promise<Response> {
	const { token, region } = await credentials();
	const res = await fetch(`https://${region}.tts.speech.microsoft.com/cognitiveservices/v1`, {
		method: 'POST',
		headers: {
			Authorization: `Bearer ${token}`,
			'Content-Type': 'application/ssml+xml',
			'X-Microsoft-OutputFormat': FORMAT
		},
		body: ssml(text)
	});
	if (!res.ok) throw new Error(`Azure text-to-speech returned ${res.status}`);
	return res;
}

async function clipFor(text: string): Promise<Blob> {
	const cache = await openCache();
	const key = cacheKey(text);
	const hit = await cache?.match(key);
	if (hit) return hit.blob();

	const res = await synthesize(text);
	await cache?.put(key, res.clone());
	return res.blob();
}

/**
 * Warms the cache for words coming up in a session, so the first play of each
 * is instant and the session keeps its audio offline. Sequential on purpose:
 * the free Azure tier allows very little concurrency. Gives up on the first
 * failure rather than retrying every item against a backend that's clearly down.
 */
export async function prefetch(texts: string[]) {
	const cache = await openCache();
	if (!cache) return;
	for (const text of texts) {
		if (!text || (await cache.match(cacheKey(text)))) continue;
		try {
			await cache.put(cacheKey(text), await synthesize(text));
		} catch {
			return;
		}
	}
}

// --- playback ----------------------------------------------------------------

let current: HTMLAudioElement | null = null;

function speakLocally(text: string, rate: number) {
	if (!speechSupported) return;
	speechSynthesis.cancel();
	const utterance = new SpeechSynthesisUtterance(text);
	utterance.lang = 'fr-FR';
	if (frenchVoice) utterance.voice = frenchVoice;
	utterance.rate = rate;
	speechSynthesis.speak(utterance);
}

export async function speak(text: string, { slow = false } = {}) {
	if (!text) return;
	stopSpeaking();
	const rate = slow ? 0.6 : settings.speechRate;
	try {
		const audio = new Audio(URL.createObjectURL(await clipFor(text)));
		audio.playbackRate = rate;
		audio.preservesPitch = true;
		audio.addEventListener('ended', () => URL.revokeObjectURL(audio.src), { once: true });
		current = audio;
		await audio.play();
	} catch {
		// no Azure key, offline on a word never played, or autoplay blocked
		speakLocally(text, rate);
	}
}

export function stopSpeaking() {
	current?.pause();
	current = null;
	if (speechSupported) speechSynthesis.cancel();
}

// --- browser fallback voice --------------------------------------------------

let frenchVoice: SpeechSynthesisVoice | null = null;

function pickVoice() {
	const voices = speechSynthesis.getVoices().filter((v) => v.lang.toLowerCase().startsWith('fr'));
	// prefer France French, and a locally installed voice (works offline)
	frenchVoice =
		voices.find((v) => v.lang === 'fr-FR' && v.localService) ??
		voices.find((v) => v.lang === 'fr-FR') ??
		voices[0] ??
		null;
}

if (speechSupported) {
	pickVoice();
	speechSynthesis.addEventListener('voiceschanged', pickVoice);
}

// --- keyboard helpers --------------------------------------------------------

export function isTypingTarget(target: EventTarget | null): boolean {
	const el = target as HTMLElement | null;
	if (!el) return false;
	if (el.tagName === 'TEXTAREA') return true;
	return el.tagName === 'INPUT' && !(el as HTMLInputElement).readOnly;
}

/** "p" plays audio, or Alt+P while typing in a field. */
export function isSpeakShortcut(e: KeyboardEvent): boolean {
	return e.code === 'KeyP' && !e.metaKey && !e.ctrlKey && (e.altKey || !isTypingTarget(e.target));
}
