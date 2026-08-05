import logging
from typing import Dict, List, Optional
from datetime import datetime, timezone
from app.routers.agent_models import (
    SessionRequestEx,
    SessionResponseEx,
    SessionErrorCode,
    SessionUsage,
    SessionResponse,
    ServerStatus,
    ServerCommand,
    Traffic
)

logger = logging.getLogger(__name__)

class VPNHoodSessionService:
    def __init__(self):
        pass

    async def create_session(self, request: SessionRequestEx) -> SessionResponseEx:
        logger.info(f"VPNHood Agent: Creating session for token {request.token_id}")
        
        # Basic validation placeholder
        if not request.token_id:
            return SessionResponseEx(
                errorCode=SessionErrorCode.Unauthorized,
                sessionId=0,
                sessionKey="",
                protocolVersion=request.protocol_version,
            )
            
        # We generate a random session ID (ulong) to represent a unique session
        # even if the same token reconnects.
        import random
        session_id = random.getrandbits(64)
        
        response = SessionResponseEx(
            errorCode=SessionErrorCode.Success,
            sessionId=session_id,
            sessionKey="dummy_session_key", # Base64 encoded byte array in real impl
            protocolVersion=request.protocol_version,
            createdTime=datetime.now(timezone.utc)
        )
        return response

    async def get_session(self, session_id: int) -> SessionResponseEx:
        logger.info(f"VPNHood Agent: Getting session {session_id}")
        # In a stateless model, if VPNHood asks about a session, we can just say it's valid
        # or we could verify it against DB if we were persisting them. For now, assume success.
        return SessionResponseEx(
            errorCode=SessionErrorCode.Success,
            sessionId=session_id,
            sessionKey="",
            protocolVersion=0
        )

    async def get_all_sessions(self) -> List[SessionResponseEx]:
        # We don't track live sessions, so return empty list to let VPNHood manage its own
        return []

    async def add_usage(self, session_id: int, traffic: Traffic, close_session: bool) -> SessionResponse:
        logger.info(f"VPNHood Agent: Adding usage to session {session_id} (close={close_session})")
        # We don't track state, so we just acknowledge the usage report.
        # In future, this usage will be persisted to the database.
            
        return SessionResponse(
            errorCode=SessionErrorCode.Success
        )

    async def add_usages(self, usages: List[SessionUsage]) -> Dict[str, SessionResponse]:
        logger.info(f"VPNHood Agent: Adding multiple usages ({len(usages)})")
        result = {}
        for usage in usages:
            # We don't remove from self._sessions here unless explicitly closed
            result[str(usage.session_id)] = SessionResponse(errorCode=SessionErrorCode.Success)
        return result

    async def update_status(self, status: ServerStatus) -> ServerCommand:
        # Keep track of VPNHood server status if necessary
        return ServerCommand(configCode=status.config_code or "default_config")
