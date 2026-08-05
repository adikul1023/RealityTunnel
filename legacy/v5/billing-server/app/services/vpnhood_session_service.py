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
    ServerInfo,
    ServerConfig,
    Traffic
)

logger = logging.getLogger(__name__)

class VPNHoodSessionService:
    def __init__(self):
        # In-memory session store for now
        self._sessions: Dict[int, SessionResponseEx] = {}
        self._next_session_id = 1

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
            
        session_id = self._next_session_id
        self._next_session_id += 1
        
        response = SessionResponseEx(
            errorCode=SessionErrorCode.Success,
            sessionId=session_id,
            sessionKey="dummy_session_key", # Base64 encoded byte array in real impl
            protocolVersion=request.protocol_version,
            createdTime=datetime.now(timezone.utc)
        )
        self._sessions[session_id] = response
        return response

    async def get_session(self, session_id: int) -> SessionResponseEx:
        logger.info(f"VPNHood Agent: Getting session {session_id}")
        if session_id in self._sessions:
            return self._sessions[session_id]
            
        return SessionResponseEx(
            errorCode=SessionErrorCode.SessionClosed,
            sessionId=session_id,
            sessionKey="",
            protocolVersion=0
        )

    async def get_all_sessions(self) -> List[SessionResponseEx]:
        return list(self._sessions.values())

    async def add_usage(self, session_id: int, traffic: Traffic, close_session: bool) -> SessionResponse:
        logger.info(f"VPNHood Agent: Adding usage to session {session_id} (close={close_session})")
        
        if close_session and session_id in self._sessions:
            del self._sessions[session_id]
            
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

    async def configure(self, info: ServerInfo) -> ServerConfig:
        logger.info(f"VPNHood Agent: Server configuration request for {info.machine_name}")
        return ServerConfig()

