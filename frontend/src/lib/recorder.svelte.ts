// The press-to-record, press-to-stop state machine, shared by the review card
// and the word-page practice panel so the flow only exists in one place.
import { assessRecording, startRecording, type Assessment, type Recording } from './pronunciation';

/** Stops a forgotten recording rather than letting it run indefinitely. */
const MAX_RECORDING_MS = 10_000;

export function createRecorder(onResult: (result: Assessment) => void) {
	let session = $state<Recording | null>(null);
	let scoring = $state(false);
	let error = $state<string | null>(null);
	let timer: ReturnType<typeof setTimeout>;

	async function stop() {
		const active = session;
		if (!active) return;
		clearTimeout(timer);
		session = null;
		scoring = true;
		try {
			onResult(await assessRecording(reference, await active.stop()));
		} catch (e) {
			error = (e as Error).message;
		} finally {
			scoring = false;
		}
	}

	let reference = '';

	return {
		get recording() {
			return session !== null;
		},
		get scoring() {
			return scoring;
		},
		get error() {
			return error;
		},
		/** Starts recording, or stops and scores if already running. */
		async toggle(referenceText: string) {
			if (session) return stop();
			if (scoring) return;
			reference = referenceText;
			error = null;
			try {
				session = await startRecording();
				timer = setTimeout(() => void stop(), MAX_RECORDING_MS);
			} catch (e) {
				error = (e as Error).message;
			}
		},
		/** Call when the component goes away, so the microphone is released. */
		dispose() {
			clearTimeout(timer);
			session?.cancel();
			session = null;
		}
	};
}
