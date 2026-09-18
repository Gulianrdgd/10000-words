// Azure Speech pronunciation assessment: records from the microphone and
// scores it against the expected French word. The SDK is imported lazily so
// it stays out of the app shell for everyone who never opens the mic.
//
// Scoring is practice-only — it never feeds FSRS. The backend hands out
// short-lived tokens; when Azure isn't configured there, this stays hidden.
import { azureAvailable, credentials } from './azure';

export interface PhonemeScore {
	phoneme: string;
	accuracy: number;
}

export interface WordScore {
	word: string;
	accuracy: number;
	/** "None" | "Mispronunciation" | "Omission" | "Insertion" */
	errorType: string;
	phonemes: PhonemeScore[];
}

export interface Assessment {
	/** 0–100, aggregated from the scores below */
	pronunciation: number;
	accuracy: number;
	fluency: number;
	completeness: number;
	recognized: string;
	words: WordScore[];
}

/** The SDK's phoneme type omits the per-phoneme AccuracyScore that the
 * service actually returns, so the phoneme list is read through this. */
type RawPhoneme = { Phoneme?: string; PronunciationAssessment?: { AccuracyScore?: number } };

export const micSupported =
	typeof navigator !== 'undefined' && !!navigator.mediaDevices?.getUserMedia;

/** False when the backend has no Azure key, so the UI can hide the feature. */
export async function pronunciationAvailable(): Promise<boolean> {
	return micSupported && (await azureAvailable());
}

export async function assess(referenceText: string): Promise<Assessment> {
	const sdk = await import('microsoft-cognitiveservices-speech-sdk');
	const { token, region } = await credentials();

	const speechConfig = sdk.SpeechConfig.fromAuthorizationToken(token, region);
	speechConfig.speechRecognitionLanguage = 'fr-FR';
	const audioConfig = sdk.AudioConfig.fromDefaultMicrophoneInput();
	const recognizer = new sdk.SpeechRecognizer(speechConfig, audioConfig);
	new sdk.PronunciationAssessmentConfig(
		referenceText,
		sdk.PronunciationAssessmentGradingSystem.HundredMark,
		sdk.PronunciationAssessmentGranularity.Phoneme,
		// miscue detection is for reading passages; on one word it just
		// re-reports what the accuracy score already says
		false
	).applyTo(recognizer);

	try {
		const result = await new Promise<import('microsoft-cognitiveservices-speech-sdk').SpeechRecognitionResult>(
			(resolve, reject) => recognizer.recognizeOnceAsync(resolve, reject)
		);
		if (result.reason === sdk.ResultReason.Canceled) {
			const details = sdk.CancellationDetails.fromResult(result);
			throw new Error(details.errorDetails || 'Azure cancelled the recognition.');
		}
		if (result.reason !== sdk.ResultReason.RecognizedSpeech) {
			throw new Error("Didn't catch that — try again a bit closer to the microphone.");
		}

		const scores = sdk.PronunciationAssessmentResult.fromResult(result);
		return {
			pronunciation: Math.round(scores.pronunciationScore),
			accuracy: Math.round(scores.accuracyScore),
			fluency: Math.round(scores.fluencyScore),
			completeness: Math.round(scores.completenessScore),
			recognized: result.text ?? '',
			words: (scores.detailResult?.Words ?? []).map((w) => ({
				word: w.Word,
				accuracy: Math.round(w.PronunciationAssessment?.AccuracyScore ?? 0),
				errorType: w.PronunciationAssessment?.ErrorType ?? 'None',
				phonemes: ((w.Phonemes ?? []) as RawPhoneme[]).map((p) => ({
					phoneme: p.Phoneme ?? '',
					accuracy: Math.round(p.PronunciationAssessment?.AccuracyScore ?? 0)
				}))
			}))
		};
	} finally {
		recognizer.close();
		audioConfig.close();
	}
}
