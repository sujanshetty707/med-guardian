import json
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from uagents import Context
from uagents_core.contrib.protocols.chat import (
    ChatMessage, ChatAcknowledgement, TextContent, MetadataContent,
    chat_protocol_spec
)
from core.db import SessionLocal, SessionState

logger = logging.getLogger("med-guardian.core.acp")

def create_ack(msg_id: uuid.UUID) -> ChatAcknowledgement:
    return ChatAcknowledgement(
        timestamp=datetime.now(timezone.utc),
        acknowledged_msg_id=msg_id
    )

def create_text_chat_message(text: str, card_data: Optional[Dict[str, Any]] = None) -> ChatMessage:
    contents = [TextContent(type="text", text=text)]
    if card_data:
        # Include metadata/card structure if available
        contents.append(MetadataContent(type="metadata", metadata=card_data))
    return ChatMessage(
        timestamp=datetime.now(timezone.utc),
        msg_id=uuid.uuid4(),
        content=contents
    )

def extract_text(msg: ChatMessage) -> str:
    texts = [c.text for c in msg.content if isinstance(c, TextContent)]
    return " ".join(texts).strip()

class SessionManager:
    @staticmethod
    def load(sender_addr: str) -> Dict[str, Any]:
        with SessionLocal() as db:
            row = db.query(SessionState).filter(SessionState.sender_addr == sender_addr).first()
            if row:
                try:
                    state = json.loads(row.state_json or "{}")
                    pending = json.loads(row.pending_action_json or "{}")
                    state["_pending_action"] = pending
                    return state
                except Exception as e:
                    logger.error(f"Error deserializing session for {sender_addr}: {e}")
            return {"sender_addr": sender_addr, "_pending_action": {}}

    @staticmethod
    def save(sender_addr: str, state: Dict[str, Any]):
        with SessionLocal() as db:
            row = db.query(SessionState).filter(SessionState.sender_addr == sender_addr).first()
            if not row:
                row = SessionState(sender_addr=sender_addr)
                db.add(row)
            
            pending = state.pop("_pending_action", {})
            row.state_json = json.dumps(state)
            row.pending_action_json = json.dumps(pending)
            row.updated_at = datetime.now(timezone.utc)
            db.commit()

sessions = SessionManager()
