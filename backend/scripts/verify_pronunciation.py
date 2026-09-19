"""Checks the pronunciation pipeline end to end, without a browser.

Azure's own text-to-speech produces known-good French speech, which is then put
through the same resampling the frontend applies to a recording and sent to the
pronunciation endpoint. A high score means the server side, the credentials and
the resampling are all sound, so any remaining fault is in browser capture.

This exists because a Firefox bug once made the app send correctly-sized,
completely silent audio, and only an out-of-browser run of the identical
arithmetic could show that the arithmetic was fine.

    AZURE_SPEECH_KEY=... AZURE_SPEECH_REGION=swedencentral \
        uv run scripts/verify_pronunciation.py [phrase]
"""
import base64
import json
import os
import struct
import sys
import urllib.request

TARGET_RATE = 16000
SOURCE_RATE = 48000
VOICE = "fr-FR-DeniseNeural"


def issue_token(key: str, region: str) -> str:
    request = urllib.request.Request(
        f"https://{region}.api.cognitive.microsoft.com/sts/v1.0/issueToken",
        data=b"",
        headers={"Ocp-Apim-Subscription-Key": key, "Content-Length": "0"},
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        return response.read().decode()


def synthesize(token: str, region: str, phrase: str) -> bytes:
    """Known-good speech at the rate a browser microphone typically runs at."""
    request = urllib.request.Request(
        f"https://{region}.tts.speech.microsoft.com/cognitiveservices/v1",
        data=(
            f'<speak version="1.0" xml:lang="fr-FR">'
            f'<voice name="{VOICE}">{phrase}</voice></speak>'
        ).encode(),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/ssml+xml",
            "X-Microsoft-OutputFormat": f"riff-{SOURCE_RATE // 1000}khz-16bit-mono-pcm",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()


def wav_samples(wav: bytes) -> list[int]:
    """Walks the RIFF chunks rather than assuming a 44-byte header."""
    offset = 12
    while offset < len(wav) - 8:
        chunk_id = wav[offset : offset + 4]
        size = struct.unpack_from("<I", wav, offset + 4)[0]
        if chunk_id == b"data":
            body = wav[offset + 8 : offset + 8 + size]
            return list(struct.unpack(f"<{len(body) // 2}h", body[: len(body) // 2 * 2]))
        offset += 8 + size + (size % 2)
    raise SystemExit("no data chunk in the synthesized WAV")


def downsample(samples: list[int], input_rate: int) -> list[int]:
    """Mirrors downsampleToPcm16 in frontend/src/lib/pronunciation.ts: averages
    each source window instead of picking every Nth sample, which would alias."""
    ratio = input_rate / TARGET_RATE
    out = []
    for i in range(int(len(samples) / ratio)):
        start = int(i * ratio)
        end = min(len(samples), int((i + 1) * ratio))
        window = samples[start:end]
        out.append(int(sum(window) / len(window)) if window else 0)
    return out


def wav_file(samples: list[int]) -> bytes:
    body = struct.pack(f"<{len(samples)}h", *samples)
    return (
        b"RIFF"
        + struct.pack("<I", 36 + len(body))
        + b"WAVEfmt "
        + struct.pack("<IHHIIHH", 16, 1, 1, TARGET_RATE, TARGET_RATE * 2, 2, 16)
        + b"data"
        + struct.pack("<I", len(body))
        + body
    )


def assess(token: str, region: str, phrase: str, wav: bytes) -> dict:
    params = json.dumps(
        {
            "ReferenceText": phrase,
            "GradingSystem": "HundredMark",
            "Granularity": "Phoneme",
            "Dimension": "Comprehensive",
            "EnableMiscue": False,
        }
    )
    request = urllib.request.Request(
        f"https://{region}.stt.speech.microsoft.com/speech/recognition/conversation"
        f"/cognitiveservices/v1?language=fr-FR&format=detailed",
        data=wav,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "audio/wav; codecs=audio/pcm; samplerate=16000",
            "Pronunciation-Assessment": base64.b64encode(params.encode()).decode(),
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read())


def main() -> int:
    key = os.environ.get("AZURE_SPEECH_KEY")
    region = os.environ.get("AZURE_SPEECH_REGION")
    if not key or not region:
        print("Set AZURE_SPEECH_KEY and AZURE_SPEECH_REGION first.")
        return 2

    phrase = " ".join(sys.argv[1:]) or "la maison"
    token = issue_token(key, region)

    source = wav_samples(synthesize(token, region, phrase))
    print(f"source:    {len(source)} samples @{SOURCE_RATE}Hz ({len(source) / SOURCE_RATE:.2f}s)")

    resampled = downsample(source, SOURCE_RATE)
    peak = max(abs(s) for s in resampled) / 32768
    print(
        f"resampled: {len(resampled)} samples @{TARGET_RATE}Hz "
        f"({len(resampled) / TARGET_RATE:.2f}s), peak {peak:.3f}"
    )

    result = assess(token, region, phrase, wav_file(resampled))
    print(f"status:    {result.get('RecognitionStatus')}")
    print(f"heard:     {result.get('DisplayText')!r}")

    best = (result.get("NBest") or [{}])[0]
    if "PronScore" not in best:
        print("\nFAIL: no pronunciation scores came back.")
        return 1

    print(
        f"scores:    pron {best['PronScore']} accuracy {best['AccuracyScore']} "
        f"fluency {best['FluencyScore']} completeness {best['CompletenessScore']}"
    )
    print("words:     " + ", ".join(f"{w['Word']}={w['AccuracyScore']}" for w in best["Words"]))

    if best["PronScore"] < 80:
        print("\nFAIL: synthesized speech should score well above 80.")
        return 1
    print("\nOK: credentials, resampling and the assessment endpoint all work.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
