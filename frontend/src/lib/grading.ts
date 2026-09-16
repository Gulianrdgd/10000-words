// Client-side mirror of the server's typed-answer grading (routers/cards.py,
// gender.py), used only to give feedback for reviews answered offline. The
// server re-grades every queued review when it syncs.
import type { DueCard } from './api';

export function levenshtein(a: string, b: string): number {
	a = a.toLowerCase().trim();
	b = b.toLowerCase().trim();
	if (a === b) return 0;
	let prev = Array.from({ length: b.length + 1 }, (_, i) => i);
	for (let i = 1; i <= a.length; i++) {
		const cur = [i];
		for (let j = 1; j <= b.length; j++) {
			cur[j] = Math.min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1));
		}
		prev = cur;
	}
	return prev[b.length];
}

const ARTICLES = new Set(['le', 'la', 'un', 'une', 'les', 'des']);

export function splitArticle(typed: string): [string | null, string] {
	const text = typed.toLowerCase().replaceAll('’', "'").split(/\s+/).filter(Boolean).join(' ');
	if (text.startsWith("l'")) return ["l'", text.slice(2).trim()];
	const [head, ...rest] = text.split(' ');
	if (ARTICLES.has(head) && rest.length) return [head, rest.join(' ')];
	return [null, text];
}

function genderCorrect(article: string | null, gender: DueCard['gender']): boolean | null {
	if (gender === 'm') return article === 'le' || article === 'un';
	if (gender === 'f') return article === 'la' || article === 'une';
	return null;
}

export function gradeLocally(
	card: DueCard,
	typed: string
): { correct: boolean; nearMiss: boolean; genderCorrect: boolean | null } {
	if (card.mode === 3 || card.pos !== 'noun') {
		const dist = levenshtein(typed, card.expected_answer ?? card.lemma);
		return { correct: dist <= 1, nearMiss: dist === 1, genderCorrect: null };
	}
	const [article, bare] = splitArticle(typed);
	const dist = levenshtein(bare, card.lemma);
	const g = genderCorrect(article, card.gender);
	const correct = dist <= 1 && g !== false;
	return { correct, nearMiss: correct && dist === 1, genderCorrect: g };
}
