// Pronunciation scoring: record a whole clip with MediaRecorder, convert it to
// 16kHz mono WAV, and post it to our backend, which forwards it to Azure.
//
// Deliberately not the Speech SDK: its browser path streams live audio through
// an AudioContext it owns, which in Firefox sent the right number of bytes and
// pure silence (NoMatch, SNR 0). Firefox's MediaRecorder also writes a
// streaming Ogg container that Azure's decoder waits on forever, hence
// decoding to WAV here. A finished clip avoids both, and needs no AudioContext,
// worklet or live resampling.
//
// Used for practice on the word page and to grade spoken reviews, where the
// score decides pass/fail and the FSRS rating.
import { BASE_URL, getToken } from './api';
import { azureAvailable } from './azure';

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

/** Opus first — it's what both Firefox and Chrome record natively, and Azure
 *  accepts it directly, so nothing has to be transcoded. */
const PREFERRED_TYPES = [
	'audio/ogg;codecs=opus',
	'audio/webm;codecs=opus',
	'audio/ogg',
	'audio/webm'
];

const micSupported =
	typeof navigator !== 'undefined' &&
	!!navigator.mediaDevices?.getUserMedia &&
	typeof MediaRecorder !== 'undefined';

/** False when the backend has no Azure key, so the UI can hide the feature. */
export async function pronunciationAvailable(): Promise<boolean> {
	return micSupported && (await azureAvailable());
}

function pickMimeType(): string {
	const supported = PREFERRED_TYPES.find((type) => MediaRecorder.isTypeSupported(type));
	if (!supported) throw new Error('This browser cannot record audio in a format Azure accepts.');
	return supported;
}

export interface Recording {
	/** Stops the microphone and resolves with what was captured. */
	stop(): Promise<Blob>;
	/** Abandons the recording and releases the microphone. */
	cancel(): void;
}

export async function startRecording(): Promise<Recording> {
	const mimeType = pickMimeType();
	let stream: MediaStream;
	try {
		stream = await navigator.mediaDevices.getUserMedia({ audio: true });
	} catch (e) {
		throw new Error(
			`Microphone unavailable (${(e as Error).name}). Allow microphone access for this site, then try again.`
		);
	}

	const recorder = new MediaRecorder(stream, { mimeType });
	const chunks: Blob[] = [];
	recorder.ondataavailable = (event) => {
		if (event.data.size > 0) chunks.push(event.data);
	};
	recorder.start();

	// Always release the device, however the recording ends: a stream left open
	// keeps the microphone busy and the next attempt captures nothing.
	const release = () => stream.getTracks().forEach((track) => track.stop());

	return {
		stop() {
			return new Promise<Blob>((resolve, reject) => {
				recorder.onstop = () => {
					release();
					const clip = new Blob(chunks, { type: mimeType });
					if (clip.size === 0) reject(new Error('Nothing was recorded — try again.'));
					else resolve(clip);
				};
				recorder.onerror = () => {
					release();
					reject(new Error('Recording failed.'));
				};
				if (recorder.state !== 'inactive') recorder.stop();
			});
		},
		cancel() {
			if (recorder.state !== 'inactive') recorder.stop();
			release();
		}
	};
}

/** Azure's pronunciation endpoint takes 16kHz mono PCM. */
const TARGET_SAMPLE_RATE = 16000;

/** Averages each source window rather than picking every Nth sample, which
 *  would alias. */
function downsampleToPcm16(input: Float32Array, inputRate: number): Int16Array {
	const ratio = inputRate / TARGET_SAMPLE_RATE;
	const out = new Int16Array(Math.floor(input.length / ratio));
	for (let i = 0; i < out.length; i++) {
		const start = Math.floor(i * ratio);
		const end = Math.min(input.length, Math.floor((i + 1) * ratio));
		let sum = 0;
		for (let j = start; j < end; j++) sum += input[j];
		const average = end > start ? sum / (end - start) : 0;
		out[i] = Math.max(-1, Math.min(1, average)) * 0x7fff;
	}
	return out;
}

function wavFile(pcm: Int16Array): Blob {
	const header = new DataView(new ArrayBuffer(44));
	const ascii = (offset: number, text: string) => {
		for (let i = 0; i < text.length; i++) header.setUint8(offset + i, text.charCodeAt(i));
	};
	ascii(0, 'RIFF');
	header.setUint32(4, 36 + pcm.byteLength, true);
	ascii(8, 'WAVEfmt ');
	header.setUint32(16, 16, true); // PCM chunk size
	header.setUint16(20, 1, true); // format: PCM
	header.setUint16(22, 1, true); // mono
	header.setUint32(24, TARGET_SAMPLE_RATE, true);
	header.setUint32(28, TARGET_SAMPLE_RATE * 2, true); // byte rate
	header.setUint16(32, 2, true); // block align
	header.setUint16(34, 16, true); // bits per sample
	ascii(36, 'data');
	header.setUint32(40, pcm.byteLength, true);
	return new Blob([header, pcm.buffer as ArrayBuffer], { type: 'audio/wav' });
}

/**
 * Converts a recording to the WAV Azure expects.
 *
 * Firefox records Ogg/Opus as a *streaming* container, and Azure's decoder
 * waits on it forever — the request simply never returns. Decoding here and
 * sending finished PCM avoids that entirely. decodeAudioData works on a
 * complete blob, so none of the live-capture problems apply.
 */
async function toWav(clip: Blob): Promise<Blob> {
	const context = new AudioContext();
	try {
		const decoded = await context.decodeAudioData(await clip.arrayBuffer());
		// Mixing to mono: a stereo capture would otherwise halve the pitch.
		let mono = decoded.getChannelData(0);
		if (decoded.numberOfChannels > 1) {
			const mixed = new Float32Array(decoded.length);
			for (let c = 0; c < decoded.numberOfChannels; c++) {
				const channel = decoded.getChannelData(c);
				for (let i = 0; i < mixed.length; i++) mixed[i] += channel[i] / decoded.numberOfChannels;
			}
			mono = mixed;
		}
		return wavFile(downsampleToPcm16(mono, decoded.sampleRate));
	} finally {
		void context.close();
	}
}

interface RestWord {
	Word: string;
	AccuracyScore?: number;
	ErrorType?: string;
	Phonemes?: { Phoneme?: string; AccuracyScore?: number }[];
	Syllables?: { Grapheme?: string; AccuracyScore?: number }[];
}

export async function assessRecording(referenceText: string, clip: Blob): Promise<Assessment> {
	// Posted to our own backend, which forwards it to Azure. Same-origin, so no
	// CORS preflight on an audio-carrying cross-origin POST, and the
	// subscription key stays server-side.
	const wav = await toWav(clip);
	const token = getToken();
	const res = await fetch(
		`${BASE_URL}/speech/assess?reference_text=${encodeURIComponent(referenceText)}`,
		{
			method: 'POST',
			headers: {
				...(token ? { Authorization: `Bearer ${token}` } : {}),
				'Content-Type': 'audio/wav'
			},
			body: wav
		}
	);
	if (!res.ok) {
		const body = await res.json().catch(() => null);
		throw new Error(body?.detail ?? `Scoring failed (${res.status}).`);
	}

	const json = await res.json();
	if (json.RecognitionStatus !== 'Success') {
		throw new Error(
			json.RecognitionStatus === 'InitialSilenceTimeout'
				? "Didn't hear anything — check the browser's microphone input, then try again."
				: "Didn't catch that — say it again, a little slower."
		);
	}

	const best = json.NBest?.[0];
	if (!best) throw new Error("Didn't catch that — say it again, a little slower.");

	return {
		pronunciation: Math.round(best.PronScore ?? 0),
		accuracy: Math.round(best.AccuracyScore ?? 0),
		fluency: Math.round(best.FluencyScore ?? 0),
		completeness: Math.round(best.CompletenessScore ?? 0),
		recognized: json.DisplayText ?? '',
		words: (best.Words ?? []).map((word: RestWord) => ({
			word: word.Word,
			accuracy: Math.round(word.AccuracyScore ?? 0),
			errorType: word.ErrorType ?? 'None',
			// French returns per-phoneme scores with empty labels, so fall back to
			// the syllable graphemes, which do carry text.
			phonemes: (word.Phonemes ?? [])
				.map((p, i) => ({
					phoneme: p.Phoneme || word.Syllables?.[i]?.Grapheme || '',
					accuracy: Math.round(p.AccuracyScore ?? 0)
				}))
				.filter((p) => p.phoneme)
		}))
	};
}
