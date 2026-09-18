import { goto } from '$app/navigation';

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '/api';
const TOKEN_KEY = 'authToken';

export class ApiError extends Error {
	constructor(
		public status: number,
		message: string
	) {
		super(message);
	}
}

export function getToken(): string | null {
	try {
		return localStorage.getItem(TOKEN_KEY);
	} catch {
		return null;
	}
}

export function setToken(token: string | null) {
	try {
		if (token) localStorage.setItem(TOKEN_KEY, token);
		else localStorage.removeItem(TOKEN_KEY);
	} catch {
		// storage unavailable (private mode): the session just won't persist
	}
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
	const token = getToken();
	const res = await fetch(`${BASE_URL}${path}`, {
		...init,
		headers: {
			'Content-Type': 'application/json',
			...(token ? { Authorization: `Bearer ${token}` } : {})
		}
	});
	if (res.status === 401 && !path.startsWith('/auth/')) {
		setToken(null);
		goto('/login');
	}
	if (!res.ok) {
		const body = await res.json().catch(() => null);
		throw new ApiError(res.status, body?.detail ?? `${res.status} ${res.statusText}`);
	}
	return res.json() as Promise<T>;
}

export interface Sentence {
	fr: string;
	en: string;
}

/** "m" | "f" | "mf" (either) | "mp" | "fp" (plural-only) | null */
export type Gender = 'm' | 'f' | 'mf' | 'mp' | 'fp' | null;

export interface DueCard {
	card_id: number;
	word_id: string;
	lemma: string;
	pos: string;
	translation_en: string;
	cefr_estimate: string;
	gender: Gender;
	display_lemma: string;
	emoji: string | null;
	track: 'recognition' | 'production';
	mode: 1 | 2 | 3 | 4 | 5 | 6;
	is_new: boolean;
	mastery_level: number;
	sentence: Sentence | null;
	options: string[] | null;
	cloze_sentence: string | null;
	expected_answer: string | null;
}

export interface DueCardsResponse {
	cards: DueCard[];
	daily_new_word_limit: number;
	new_words_introduced_today: number;
}

export interface ReviewRequest {
	mode: number;
	correct?: boolean;
	latency_ms?: number;
	typed_answer?: string;
	self_reported_correct?: boolean;
	expected_answer?: string;
	pronunciation_score?: number;
	phonemes?: { p: string; a: number }[];
	client_review_id?: string;
	reviewed_at?: string;
}

export interface ReviewResponse {
	card_id: number;
	word_id: string;
	track: string;
	rating: number;
	correct: boolean;
	near_miss: boolean;
	gender_correct: boolean | null;
	expected_answer: string | null;
	/** null when graded locally while offline */
	interval_days: number | null;
	mastery_level: number;
	word_mastered: boolean;
	streak: number | null;
	offline?: boolean;
}

export interface GoalResponse {
	week_start: string;
	target_words: number;
	achieved_words: number;
	days_remaining: number;
}

export interface WeekReviewResponse {
	week_start: string;
	mastered_words: string[];
	shaky_words: string[];
	growth_stat: string;
	target_words: number;
	achieved_words: number;
}

export interface GrowthPoint {
	date: string;
	cumulative_mastered: number;
}

export interface GrowthResponse {
	points: GrowthPoint[];
	total_words_in_deck: number;
	coverage_percent: number;
	current_streak: number;
	longest_streak: number;
}

export interface ActivityDay {
	date: string;
	reviews: number;
	correct: number;
}

export interface SpokenWordStat {
	word_id: string;
	lemma: string;
	display_lemma: string;
	translation_en: string;
	average_score: number;
	last_score: number;
	attempts: number;
}

export interface PhonemeStat {
	phoneme: string;
	average_accuracy: number;
	samples: number;
}

export interface PronunciationStats {
	attempts: number;
	average_score: number | null;
	worst_words: SpokenWordStat[];
	weak_phonemes: PhonemeStat[];
}

export interface WordProgress {
	id: string;
	lemma: string;
	display_lemma: string;
	gender: Gender;
	emoji: string | null;
	pos: string;
	translation_en: string;
	frequency_rank: number;
	cefr_estimate: string;
	recognition_mastery: number;
	production_mastery: number;
	mastered: boolean;
}

export interface WordDetail {
	id: string;
	lemma: string;
	display_lemma: string;
	gender: Gender;
	emoji: string | null;
	pos: string;
	translation_en: string;
	frequency_rank: number;
	cefr_estimate: string;
	sentences: Sentence[];
	tracks: {
		track: string;
		introduced: boolean;
		mastery_level: number;
		reps: number;
		lapses: number;
		due_date: string | null;
		last_review: string | null;
		/** FSRS days until recall drops to 90% — what mastery is judged on */
		stability_days: number | null;
	}[];
	reviews: {
		timestamp: string;
		track: string;
		mode: number;
		correct: boolean;
		near_miss: boolean;
		gender_correct: boolean | null;
	}[];
	mastered_at: string | null;
}

export interface AuthResponse {
	token: string;
	username: string;
}

export interface PushStatus {
	subscribed: boolean;
	reminder_hour: number | null;
}

const post = <T>(path: string, body: unknown) =>
	request<T>(path, { method: 'POST', body: JSON.stringify(body) });

/**
 * The full deck is ~2.4 MB of JSON (gzipped to ~220 KB by the server), so it's
 * held for the life of the page: navigating progress -> word -> back is
 * instant instead of refetching. Stale-while-revalidate — the cached copy is
 * returned at once and a refresh runs behind it, since mastery shifts with
 * every review.
 */
let wordsCache: WordProgress[] | null = null;

function refreshWords(): Promise<WordProgress[]> {
	return request<WordProgress[]>('/words').then((w) => (wordsCache = w));
}

export function getWordsCached(): Promise<WordProgress[]> {
	if (!wordsCache) return refreshWords();
	const cached = wordsCache;
	refreshWords().catch(() => {});
	return Promise.resolve(cached);
}

export function clearWordsCache() {
	wordsCache = null;
}

export const api = {
	register: (username: string, password: string) =>
		post<AuthResponse>('/auth/register', { username, password }),
	login: (username: string, password: string) =>
		post<AuthResponse>('/auth/login', { username, password }),
	logout: () => post<{ ok: boolean }>('/auth/logout', {}),
	me: () => request<{ username: string }>('/auth/me'),

	getDueCards: (limit = 30, extraNew = 0) =>
		request<DueCardsResponse>(`/cards/due?limit=${limit}&extra_new=${extraNew}`),
	submitReview: (cardId: number, body: ReviewRequest) =>
		post<ReviewResponse>(`/cards/${cardId}/review`, body),
	getCurrentGoal: () => request<GoalResponse>('/goals/current'),
	setGoal: (targetWords: number) => post<GoalResponse>('/goals', { target_words: targetWords }),
	getWeekReview: (week: string) => request<WeekReviewResponse>(`/goals/${week}/review`),
	getGrowth: () => request<GrowthResponse>('/stats/growth'),
	getActivity: (days = 140) => request<{ days: ActivityDay[] }>(`/stats/activity?days=${days}`),
	getPronunciationStats: () => request<PronunciationStats>('/stats/pronunciation'),
	getWords: () => request<WordProgress[]>('/words'),
	getWord: (id: string) => request<WordDetail>(`/words/${encodeURIComponent(id)}`),

	getSpeechToken: () => request<{ token: string; region: string }>('/speech/token'),

	getPushPublicKey: () => request<{ public_key: string }>('/push/public-key'),
	getPushStatus: (endpoint: string) =>
		request<PushStatus>(`/push/status?endpoint=${encodeURIComponent(endpoint)}`),
	subscribePush: (sub: PushSubscriptionJSON, timezone: string, reminderHour: number) =>
		post<PushStatus>('/push/subscribe', {
			endpoint: sub.endpoint,
			keys: sub.keys,
			timezone,
			reminder_hour: reminderHour
		}),
	unsubscribePush: (endpoint: string) => post<PushStatus>('/push/unsubscribe', { endpoint }),
	testPush: (endpoint: string) => post<{ ok: boolean }>('/push/test', { endpoint })
};
