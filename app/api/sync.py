"""
Sync API Endpoints
Handles card queue management for cloud-to-local synchronization
"""

from fastapi import APIRouter, Header, HTTPException, Depends
from sqlalchemy.orm import Session
from app.db.session import get_db_session
from app.models.card_queue import CardQueue
from app.config import settings
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import os

router = APIRouter()

# Get sync secret from environment (set in Railway)
SYNC_SECRET = os.getenv("SYNC_SECRET", "development_secret_change_in_production")


class QueueCardRequest(BaseModel):
    """Request to queue a card for sync"""
    hanzi: str
    pinyin: str
    definition: str
    sentence_hanzi: Optional[str] = None
    sentence_pinyin: Optional[str] = None
    sentence_english: Optional[str] = None
    audio_url: Optional[str] = None
    hsk_level: Optional[int] = None
    part_of_speech: Optional[str] = None


class AcknowledgeRequest(BaseModel):
    """Request to acknowledge synced cards"""
    ids: List[int]


def verify_sync_secret(x_sync_secret: str = Header(None)):
    """Verify sync secret authentication"""
    if x_sync_secret != SYNC_SECRET:
        raise HTTPException(status_code=401, detail="Invalid sync secret")
    return True


@router.post("/queue")
def queue_card(request: QueueCardRequest, db: Session = Depends(get_db_session)):
    """
    Queue a card for later synchronization to local Anki
    This replaces direct AnkiConnect calls when deployed to cloud
    """
    card = CardQueue(
        hanzi=request.hanzi,
        pinyin=request.pinyin,
        definition=request.definition,
        sentence_hanzi=request.sentence_hanzi,
        sentence_pinyin=request.sentence_pinyin,
        sentence_english=request.sentence_english,
        audio_url=request.audio_url,
        hsk_level=request.hsk_level,
        part_of_speech=request.part_of_speech,
        status="pending"
    )
    
    db.add(card)
    db.commit()
    db.refresh(card)
    
    # Count total pending cards
    pending_count = db.query(CardQueue).filter(CardQueue.status == "pending").count()
    
    return {
        "queued": True,
        "card_id": card.id,
        "queue_position": pending_count,
        "message": f"Card queued for sync ({pending_count} pending)"
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
