"""
Sync API Endpoints
Handles card queue management for cloud-to-local synchronization
"""

from fastapi import APIRouter, Header, HTTPException, Depends, Request
from sqlalchemy.orm import Session
from app.db.session import get_db_session
from app.models.card_queue import CardQueue
from app.services.service_cache import get_settings as _get_settings
from app.config import settings
from app.middleware.rate_limit import limiter
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import secrets as _secrets

router = APIRouter()

# Sync secret is now centrally managed by Pydantic Settings (see app/config.py).
# Kept as a module-level alias for backwards-compat with the verify function.
SYNC_SECRET = settings.sync_secret


class QueueCardRequest(BaseModel):
    """Request to queue a card for sync"""
    hanzi: str
    pinyin: str
    definition: str
    sentence_hanzi: Optional[str] = None
    sentence_pinyin: Optional[str] = None
    sentence_english: Optional[str] = None
    audio_url: Optional[str] = None
    hint: Optional[str] = None
    hsk_level: Optional[int] = None
    part_of_speech: Optional[str] = None


class AcknowledgeRequest(BaseModel):
    """Request to acknowledge synced cards"""
    ids: List[int]


def verify_sync_secret(x_sync_secret: str = Header(None)):
    """Verify sync secret authentication (timing-safe comparison)"""
    if not _secrets.compare_digest(x_sync_secret or "", SYNC_SECRET):
        raise HTTPException(status_code=401, detail="Invalid sync secret")
    return True


@router.post("/queue")
@limiter.limit("30/minute")
def queue_card(
    request: Request,
    payload: QueueCardRequest,
    db: Session = Depends(get_db_session),
):
    """
    Queue 2 or 4 Anki cards for later sync to local Anki.

    Normal mode (4 cards): EN→ZH, ZH→EN, EN Sentence→ZH Sentence, ZH Sentence (cloze).
    Strict mode (2 cards): ZH→EN + ZH Sentence (cloze) only.

    Sentence card types are skipped if no sentence_hanzi is provided.

    Rate-limited to 30 requests/minute per IP — slowapi requires a `request:
    Request` parameter so the decorator can extract the client address.
    """
    db_settings = _get_settings(db)
    strict_mode = bool(db_settings.strict_mode) if db_settings else False

    if strict_mode:
        card_types = ["zh_to_en", "zh_sentence"]
    else:
        card_types = ["en_to_zh", "zh_to_en", "en_sentence", "zh_sentence"]

    # Drop sentence-type cards when no sentence data is available
    has_sentence = bool(payload.sentence_hanzi)
    if not has_sentence:
        card_types = [ct for ct in card_types if "sentence" not in ct]

    for card_type in card_types:
        card = CardQueue(
            hanzi=payload.hanzi,
            pinyin=payload.pinyin,
            definition=payload.definition,
            sentence_hanzi=payload.sentence_hanzi,
            sentence_pinyin=payload.sentence_pinyin,
            sentence_english=payload.sentence_english,
            audio_url=payload.audio_url,
            hint=payload.hint,
            card_type=card_type,
            hsk_level=payload.hsk_level,
            part_of_speech=payload.part_of_speech,
            status="pending",
        )
        db.add(card)

    db.commit()

    pending_count = db.query(CardQueue).filter(CardQueue.status == "pending").count()
    cards_created = len(card_types)

    return {
        "queued": True,
        "cards_created": cards_created,
        "queue_position": pending_count,
        "message": f"{cards_created} card(s) queued for sync",
    }


@router.get("/pending")
def get_pending_cards(
    db: Session = Depends(get_db_session),
    authenticated: bool = Depends(verify_sync_secret)
):
    """
    Get all pending cards waiting for sync
    Requires SYNC_SECRET authentication header
    """
    cards = db.query(CardQueue).filter(CardQueue.status == "pending").order_by(CardQueue.created_at).all()
    
    return {
        "pending_count": len(cards),
        "cards": [card.to_dict() for card in cards]
    }


@router.post("/ack")
def acknowledge_synced_cards(
    request: AcknowledgeRequest,
    db: Session = Depends(get_db_session),
    authenticated: bool = Depends(verify_sync_secret)
):
    """
    Mark cards as successfully synced
    Requires SYNC_SECRET authentication header
    """
    synced_count = 0
    
    for card_id in request.ids:
        card = db.query(CardQueue).filter(CardQueue.id == card_id).first()
        if card:
            card.status = "synced"
            card.synced_at = datetime.utcnow()
            synced_count += 1
    
    db.commit()
    
    return {
        "synced_count": synced_count,
        "message": f"Marked {synced_count} card(s) as synced"
    }


@router.get("/stats")
def get_sync_stats(db: Session = Depends(get_db_session)):
    """Get synchronization statistics (public endpoint for UI)"""
    pending = db.query(CardQueue).filter(CardQueue.status == "pending").count()
    synced = db.query(CardQueue).filter(CardQueue.status == "synced").count()
    failed = db.query(CardQueue).filter(CardQueue.status == "failed").count()
    
    return {
        "pending": pending,
        "synced": synced,
        "failed": failed,
        "total": pending + synced + failed
    }


@router.delete("/clear-synced")
def clear_synced_cards(
    db: Session = Depends(get_db_session),
    authenticated: bool = Depends(verify_sync_secret)
):
    """
    Delete all synced cards from queue (housekeeping)
    Requires SYNC_SECRET authentication header
    """
    deleted = db.query(CardQueue).filter(CardQueue.status == "synced").delete()
    db.commit()
    
    return {
        "deleted_count": deleted,
        "message": f"Cleared {deleted} synced card(s)"
    }
