"""Short-lived Azure Speech tokens for in-browser pronunciation assessment.

The subscription key stays on the server; the browser gets a 10-minute token
it trades directly with Azure. Unset AZURE_SPEECH_KEY/AZURE_SPEECH_REGION
(the default) returns 503 and the frontend hides the feature.
"""
import os
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException

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
    return SpeechToken(token=_cached[0], region=region)
