// Offline support: reviews that can't reach the server are queued in
// localStorage and replayed in order once it's reachable again. Each carries
// a client_review_id (so a replay is never applied twice) and its real answer
// time (so FSRS schedules from when it was actually answered). The current
// session's remaining cards are cached too, so a session can start offline.
import { api, ApiError, type DueCard, type ReviewRequest, type ReviewResponse } from './api';
import { gradeLocally } from './grading';

const QUEUE_KEY = 'pendingReviews';
const SESSION_KEY = 'sessionCards';

interface QueuedReview {
	cardId: number;
	body: ReviewRequest;
}

function read<T>(key: string, fallback: T): T {
	try {
		const raw = localStorage.getItem(key);
		return raw ? (JSON.parse(raw) as T) : fallback;
	} catch {
		return fallback;
	}
}

function write(key: string, value: unknown) {
	try {
		localStorage.setItem(key, JSON.stringify(value));
	} catch {
		// storage full/unavailable: offline queueing degrades to in-memory only
	}
}

export const sync = $state({
	pending: read<QueuedReview[]>(QUEUE_KEY, []).length,
	online: typeof navigator === 'undefined' ? true : navigator.onLine
});

/** Network failure or server unavailable, as opposed to a request the server rejected. */
function isUnreachable(e: unknown): boolean {
	return !(e instanceof ApiError) || e.status >= 500;
}

function newId(): string {
	return crypto.randomUUID?.() ?? `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

export async function submitReview(
	card: DueCard,
	body: ReviewRequest,
	typedAnswer?: string
): Promise<ReviewResponse> {
	const full: ReviewRequest = {
		...body,
		client_review_id: newId(),
		reviewed_at: new Date().toISOString()
	};
	if (card.mode === 3 && card.expected_answer) full.expected_answer = card.expected_answer;

	// Keep replay order: while older reviews are still queued, queue this one too.
	if (sync.pending === 0) {
		try {
			const res = await api.submitReview(card.card_id, full);
			sync.online = true;
			return res;
		} catch (e) {
			if (!isUnreachable(e)) throw e;
			sync.online = false;
		}
	}

	const queue = read<QueuedReview[]>(QUEUE_KEY, []);
	queue.push({ cardId: card.card_id, body: full });
	write(QUEUE_KEY, queue);
	sync.pending = queue.length;
	flushQueue(); // fails fast if still offline

	return localResponse(card, full, typedAnswer);
}

function localResponse(card: DueCard, body: ReviewRequest, typed?: string): ReviewResponse {
	let correct: boolean;
	let nearMiss = false;
	let genderCorrect: boolean | null = null;
	if (card.mode === 2 || card.mode === 3 || card.mode === 5) {
		({ correct, nearMiss, genderCorrect } = gradeLocally(card, typed ?? ''));
	} else {
		correct = card.mode === 4 ? !!body.self_reported_correct : !!body.correct;
	}
	return {
		card_id: card.card_id,
		word_id: card.word_id,
		track: card.track,
		rating: 0,
		correct,
		near_miss: nearMiss,
		gender_correct: genderCorrect,
		expected_answer: card.mode === 1 || card.mode === 4 ? null : card.expected_answer,
		interval_days: null,
		mastery_level: card.mastery_level,
		word_mastered: false,
		streak: null,
		offline: true
	};
}

let flushing: Promise<void> | null = null;

/** Replays queued reviews in order; stops at the first one the server can't take yet. */
export function flushQueue(): Promise<void> {
	// reset via .finally (always async) so it runs after the assignment, even
	// when there's nothing to flush and the body completes synchronously
	flushing ??= replayQueue().finally(() => (flushing = null));
	return flushing;
}

async function replayQueue(): Promise<void> {
	let queue = read<QueuedReview[]>(QUEUE_KEY, []);
	while (queue.length > 0) {
		const [next] = queue;
		try {
			await api.submitReview(next.cardId, next.body);
			sync.online = true;
		} catch (e) {
			if (isUnreachable(e) || (e instanceof ApiError && e.status === 401)) {
				if (isUnreachable(e)) sync.online = false;
				return;
			}
			// rejected outright (e.g. card no longer exists): drop it rather than block the queue
		}
		queue = read<QueuedReview[]>(QUEUE_KEY, []).slice(1);
		write(QUEUE_KEY, queue);
		sync.pending = queue.length;
	}
}

export function saveSessionCards(cards: DueCard[]) {
	write(SESSION_KEY, cards);
}

export function loadSessionCards(): DueCard[] {
	return read<DueCard[]>(SESSION_KEY, []);
}

export function clearOfflineData() {
	try {
		localStorage.removeItem(QUEUE_KEY);
		localStorage.removeItem(SESSION_KEY);
	} catch {
		// nothing to clear
	}
	sync.pending = 0;
}

if (typeof window !== 'undefined') {
	window.addEventListener('online', () => {
		sync.online = true;
		// the connection often isn't usable the instant the event fires
		setTimeout(flushQueue, 1000);
	});
	window.addEventListener('offline', () => (sync.online = false));
}
