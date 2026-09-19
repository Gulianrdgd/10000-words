"""Azure Speech endpoints.

/assess proxies a recorded clip to Azure's pronunciation REST API, keeping the
request same-origin and the subscription key server-side. /token mints the
short-lived token the browser uses for text-to-speech only.

Unset AZURE_SPEECH_KEY/AZURE_SPEECH_REGION (the default) returns 503 and the
frontend hides the feature.
"""
import base64
import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.auth import get_current_user_id
from app.schemas import SpeechToken

router = APIRouter(prefix="/speech", tags=["speech"])

# Azure issues 10-minute tokens; refresh a little early.
TOKEN_LIFETIME = timedelta(minutes=9)

_cached: tuple[str, datetime] | None = None


def _issue_token(key: str, region: str) -> str:
    request = urllib.request.Request(
        f"https://{region}.api.cognitive.microsoft.com/sts/v1.0/issueToken",
        data=b"",
        headers={"Ocp-Apim-Subscription-Key": key, "Content-Length": "0"},
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        return response.read().decode()


@router.post("/assess")
async def assess(
    request: Request,
    reference_text: str = Query(min_length=1, max_length=500),
    _user_id: str = Depends(get_current_user_id),
):
    """Scores a recorded clip, proxying it to Azure's REST endpoint.

    Going through the backend rather than calling Azure from the browser keeps
    the request same-origin (no CORS preflight on a cross-origin POST carrying
    an audio body) and means the subscription key never reaches the browser.
    """
    key = os.environ.get("AZURE_SPEECH_KEY")
    region = os.environ.get("AZURE_SPEECH_REGION")
    if not key or not region:
        raise HTTPException(status_code=503, detail="Pronunciation scoring is not configured.")

    audio = await request.body()
    if not audio:
        raise HTTPException(status_code=400, detail="No audio received.")

    params = json.dumps(
        {
            "ReferenceText": reference_text,
            "GradingSystem": "HundredMark",
            "Granularity": "Phoneme",
            "Dimension": "Comprehensive",
            "EnableMiscue": False,
        }
    )
    # The browser decodes its recording and sends finished 16kHz mono PCM:
    # Azure's decoder hangs forever on Firefox's streaming Ogg/Opus container.
    content_type = "audio/wav; codecs=audio/pcm; samplerate=16000"

    proxied = urllib.request.Request(
        f"https://{region}.stt.speech.microsoft.com/speech/recognition/conversation"
        f"/cognitiveservices/v1?language=fr-FR&format=detailed",
        data=audio,
        headers={
            "Ocp-Apim-Subscription-Key": key,
            "Content-Type": content_type,
            "Pronunciation-Assessment": base64.b64encode(params.encode()).decode(),
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(proxied, timeout=30) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:200]
        raise HTTPException(status_code=502, detail=f"Azure returned {e.code}: {detail}") from e
    except (urllib.error.URLError, TimeoutError) as e:
        raise HTTPException(status_code=504, detail=f"Azure unreachable: {e}") from e


@router.get("/token", response_model=SpeechToken)
def token(_user_id: str = Depends(get_current_user_id)):
    global _cached
    key = os.environ.get("AZURE_SPEECH_KEY")
    region = os.environ.get("AZURE_SPEECH_REGION")
    if not key or not region:
        raise HTTPException(status_code=503, detail="Pronunciation scoring is not configured.")

    now = datetime.now(timezone.utc)
    if _cached is None or _cached[1] <= now:
        try:
            _cached = (_issue_token(key, region), now + TOKEN_LIFETIME)
        except (urllib.error.URLError, TimeoutError) as e:
            raise HTTPException(status_code=502, detail=f"Azure Speech rejected the key: {e}") from e
    # The remaining life of *this* token, not a fresh one: a cached token handed
    # out at minute 8 has a minute left, and a client assuming otherwise would
    # keep using it well past expiry.
    return SpeechToken(
        token=_cached[0],
        region=region,
        expires_in_seconds=max(0, int((_cached[1] - now).total_seconds())),
    )
