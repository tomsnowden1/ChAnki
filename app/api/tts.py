"""
Text-to-Speech endpoint backed by edge-tts.

Provides high-quality Mandarin audio for the in-app 🔊 button. The browser
SpeechSynthesis API produces robotic Mandarin on most desktops and refuses
zh-CN entirely on iOS Safari, so we render audio server-side with edge-tts
(Microsoft Edge's neural voices) instead.

The actual audio generation is handled by `app/services/audio.py:AudioService`
which is already async and was already wired up for card-creation; this
endpoint exposes it directly to the frontend.
"""
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
from app.services.audio import AudioService
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["tts"])

# Module-level singleton — AudioService is just a config wrapper, not a connection
_audio = AudioService()

# Generous but bounded — typical sentences are <50 chars; this stops abuse
_MAX_TEXT_LEN = 200


@router.get("/tts")
async def synthesize(
    text: str = Query(..., min_length=1, description="Chinese text to synthesize"),
):
    """
    Stream Mandarin audio (audio/mpeg) for the given text.

    Cached by URL on the client (Cache-Control: public, max-age=86400) so
    repeat playbacks don't re-hit edge-tts.
    """
    if len(text) > _MAX_TEXT_LEN:
        raise HTTPException(
            status_code=413,
            detail=f"Text too long ({len(text)} > {_MAX_TEXT_LEN})",
        )

    audio = await _audio.generate_audio_async(text)
    if not audio:
        raise HTTPException(status_code=502, detail="Edge-TTS returned no audio")

    return Response(
        content=audio,
        media_type="audio/mpeg",
        headers={
            # Browser caches by URL (i.e. by the encoded text), so subsequent
            # plays of the same word are instant.
            "Cache-Control": "public, max-age=86400, immutable",
        },
    )
