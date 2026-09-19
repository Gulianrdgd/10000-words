// Short-lived Azure Speech tokens, shared by neural text-to-speech and
// pronunciation scoring. The subscription key stays on the backend; this only
// ever handles the 10-minute token it hands out.
import { api } from './api';

let cached: { token: string; region: string; expiresAt: number } | null = null;
/** Set after a failed fetch so an unconfigured backend isn't asked on every
 *  single play — otherwise each speak() would cost a round-trip to a 503. */
let retryAfter = 0;

export async function credentials(): Promise<{ token: string; region: string }> {
	if (cached && cached.expiresAt > Date.now()) return cached;
	if (Date.now() < retryAfter) throw new Error('Azure Speech is unavailable.');
	try {
		const { token, region, expires_in_seconds } = await api.getSpeechToken();
		// Trust the server's remaining lifetime rather than assuming a fresh
		// token: the backend caches these, so one can arrive nearly expired.
		// The 30s margin covers a slow request mid-session.
		const lifetime = Math.max(0, expires_in_seconds * 1000 - 30_000);
		cached = { token, region, expiresAt: Date.now() + lifetime };
		return cached;
	} catch (e) {
		retryAfter = Date.now() + 5 * 60_000;
		throw e;
	}
}

/** False when the backend has no Azure key, so callers can hide the feature. */
export async function azureAvailable(): Promise<boolean> {
	try {
		await credentials();
		return true;
	} catch {
		return false;
	}
}
