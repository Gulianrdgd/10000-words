const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '/api';

async function request<T>(path: string, init?: RequestInit): Promise<T> {
	const res = await fetch(`${BASE_URL}${path}`, {
		headers: { 'Content-Type': 'application/json' },
		...init
	});
	if (!res.ok) {
		const body = await res.text().catch(() => '');
		throw new Error(`${res.status} ${res.statusText}: ${body}`);
	}
	return res.json() as Promise<T>;
}

export interface Sentence {
	fr: string;
	en: string;
}

export interface DueCard {
	card_id: number;
	word_id: string;
	lemma: string;
	pos: string;
	translation_en: string;
	cefr_estimate: string;
	track: 'recognition' | 'production';
	mode: 1 | 2 | 3 | 4;
	is_new: boolean;
	mastery_level: number;
	sentence: Sentence | null;
	options: string[] | null;
	cloze_sentence: string | null;
}

export interface DueCardsResponse {
	cards: DueCard[];
	daily_new_word_limit: number;
	new_words_introduced_today: number;
}

export interface ReviewRequest {
	mode: number;
	correct: boolean;
	latency_ms?: number;
	typed_answer?: string;
	self_reported_correct?: boolean;
}

export interface ReviewResponse {
	card_id: number;
	word_id: string;
	track: string;
	rating: number;
	correct: boolean;
	near_miss: boolean;
	expected_answer: string | null;
	interval_days: number;
	mastery_level: number;
	word_mastered: boolean;
	streak: number;
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

export interface WordProgress {
	id: string;
	lemma: string;
	pos: string;
	translation_en: string;
	frequency_rank: number;
	cefr_estimate: string;
	recognition_mastery: number;
	production_mastery: number;
	mastered: boolean;
}

export const api = {
	getDueCards: (limit = 30) => request<DueCardsResponse>(`/cards/due?limit=${limit}`),
	submitReview: (cardId: number, body: ReviewRequest) =>
		request<ReviewResponse>(`/cards/${cardId}/review`, {
			method: 'POST',
			body: JSON.stringify(body)
		}),
	getCurrentGoal: () => request<GoalResponse>('/goals/current'),
	setGoal: (targetWords: number) =>
		request<GoalResponse>('/goals', {
			method: 'POST',
			body: JSON.stringify({ target_words: targetWords })
		}),
	getWeekReview: (week: string) => request<WeekReviewResponse>(`/goals/${week}/review`),
	getGrowth: () => request<GrowthResponse>('/stats/growth'),
	getWords: () => request<WordProgress[]>('/words')
};
