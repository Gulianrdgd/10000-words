// Per-device preferences, persisted to localStorage.
const KEY = 'settings';

interface Settings {
	sessionSize: number;
	autoplayAudio: boolean;
	speechRate: number;
}

const defaults: Settings = { sessionSize: 20, autoplayAudio: true, speechRate: 0.9 };

function load(): Settings {
	try {
		return { ...defaults, ...JSON.parse(localStorage.getItem(KEY) ?? '{}') };
	} catch {
		return defaults;
	}
}

export const settings = $state<Settings>(load());

export function saveSettings() {
	try {
		localStorage.setItem(KEY, JSON.stringify(settings));
	} catch {
		// storage unavailable: settings last for this visit only
	}
}
