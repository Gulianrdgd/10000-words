// French text-to-speech via the browser's built-in Web Speech API: free,
// offline-capable on most devices, no backend involved.
import { settings } from './settings.svelte';

export const speechSupported = typeof window !== 'undefined' && 'speechSynthesis' in window;

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

export function speak(text: string, { slow = false } = {}) {
	if (!speechSupported || !text) return;
	speechSynthesis.cancel();
	const utterance = new SpeechSynthesisUtterance(text);
	utterance.lang = 'fr-FR';
	if (frenchVoice) utterance.voice = frenchVoice;
	utterance.rate = slow ? 0.6 : settings.speechRate;
	speechSynthesis.speak(utterance);
}

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
