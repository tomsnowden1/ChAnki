"""
API endpoint to generate 3 sentences for preview (before adding to Anki).

Tatoeba is the primary source; Gemini is the fallback when Tatoeba lacks
enough hits for the queried word.
"""
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from app.db.session import get_db_session
from app.services.service_cache import get_gemini, get_settings, get_sentence_service
from app.config import settings as env_settings
from pydantic import BaseModel
from typing import Optional, List, Dict
import asyncio
import json
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["sentences"])


class GenerateSentencesRequest(BaseModel):
    hanzi: str
    pinyin: str
    definition: str
    hsk_level: Optional[int] = 3


class GenerateSentencesResponse(BaseModel):
    success: bool
    sentences: List[Dict[str, str]]
    message: Optional[str] = None


@router.post("/generate-sentences", response_model=GenerateSentencesResponse)
async def generate_sentences(
    request: GenerateSentencesRequest,
    db: Session = Depends(get_db_session)
):
    """Generate 3 example sentences. Tries Tatoeba first, then Gemini."""
    try:
        settings = get_settings(db)
        gemini = None
        api_key = (settings.gemini_api_key if settings else "") or env_settings.gemini_api_key
        if api_key:
            gemini = get_gemini(api_key)

        service = get_sentence_service(db, gemini)
        sentences = await service.find_sentences_async(
            request.hanzi,
            request.pinyin,
            request.definition,
            request.hsk_level or 3,
        )

        if not sentences:
            return GenerateSentencesResponse(
                success=False,
                sentences=[],
                message=(
                    "No Tatoeba match and no Gemini key configured. "
                    "Add a Gemini key in Settings to enable AI fallback."
                    if gemini is None
                    else "No sentences found."
                ),
            )

        return GenerateSentencesResponse(success=True, sentences=sentences)

    except Exception as e:
        return GenerateSentencesResponse(
            success=False,
            sentences=[],
            message=f"Error: {str(e)}",
        )


@router.get("/generate-sentences/stream")
async def generate_sentences_stream(
    hanzi: str,
    pinyin: str = "",
    definition: str = "",
    hsk_level: int = 3,
    db: Session = Depends(get_db_session),
):
    """
    Server-sent events stream of example sentences.

    Each sentence is emitted as a `data: {...}` event the moment it's ready
    — Tatoeba hits first (instant), then any Gemini fallback streams in as
    Gemini emits each line of NDJSON. First sentence in <1s instead of
    waiting 2-3s for the full batch.

    SSE protocol:
      data: {"hanzi":"...","pinyin":"...","english":"...","hint":"...","source":"..."}
      : ping            (heartbeat every 15s; defeats Render's 100s idle timeout)
      event: done
      data: {}

    Frontend uses `EventSource(...)` to consume. GET-only because that's
    EventSource's only mode; the older POST endpoint stays for fallback.
    """
    settings_row = get_settings(db)
    api_key = (settings_row.gemini_api_key if settings_row else "") or env_settings.gemini_api_key
    gemini = get_gemini(api_key) if api_key else None

    service = get_sentence_service(db, gemini)
    target_count = 3

    async def event_stream():
        # 1. Tatoeba results stream in first (these are already in-memory)
        tatoeba_rows = service._tatoeba_lookup(hanzi, hsk_level, target_count)
        for r in tatoeba_rows:
            payload = service._row_to_dict(r)
            yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

        # 2. Gemini fallback streams in for any remaining slots
        emitted_from_gemini = []
        needed = target_count - len(tatoeba_rows)
        if needed > 0 and gemini is not None:
            sent = 0
            async for s in gemini.generate_sentences_stream(hanzi, pinyin, definition, hsk_level):
                if "error" in s:
                    yield f"event: error\ndata: {json.dumps(s, ensure_ascii=False)}\n\n"
                    break
                payload = {**s, "source": "gemini"}
                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
                emitted_from_gemini.append(s)
                sent += 1
                if sent >= needed:
                    break

            # 3. Persist Gemini sentences for future cache hits.
            # Done after streaming so the user sees results immediately;
            # the DB write is fire-and-forget from the client's perspective.
            if emitted_from_gemini:
                try:
                    service._persist_gemini_results(
                        hanzi, hsk_level, emitted_from_gemini, len(emitted_from_gemini)
                    )
                except Exception as e:
                    logger.warning(f"Persisting streamed Gemini sentences failed: {e}")

        # 4. Closing event so the client can call EventSource.close()
        yield "event: done\ndata: {}\n\n"

    async def with_heartbeat():
        """Wrap the stream with periodic comment-line heartbeats every 15s.
        Defeats Render's 100s idle-cut without changing event semantics —
        SSE comment lines (`:` prefix) are silently discarded by EventSource."""
        agen = event_stream().__aiter__()
        next_task = asyncio.ensure_future(agen.__anext__())
        try:
            while True:
                done, _ = await asyncio.wait({next_task}, timeout=15.0)
                if not done:
                    yield ": ping\n\n"
                    continue
                # Real event arrived (or stream ended)
                try:
                    yield next_task.result()
                except StopAsyncIteration:
                    return
                next_task = asyncio.ensure_future(agen.__anext__())
        finally:
            if not next_task.done():
                next_task.cancel()

    return StreamingResponse(
        with_heartbeat(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            # Defensive: tell any nginx-style intermediary not to buffer
            "X-Accel-Buffering": "no",
        },
    )
