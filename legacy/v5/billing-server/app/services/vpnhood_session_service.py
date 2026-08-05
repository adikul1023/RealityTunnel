import logging
from typing import Dict, List, Optional
from datetime import datetime, timezone
from app.config import settings
from app.routers.agent_models import (
    SessionRequestEx,
    SessionResponseEx,
    SessionErrorCode,
    SessionUsage,
    SessionResponse,
    ServerStatus,
    ServerCommand,
    Traffic,
    ServerInfo,
    ServerConfig
)

logger = logging.getLogger(__name__)

class VPNHoodSessionService:
    def __init__(self):
        self._registered_servers = set()

    async def configure(self, server_info: ServerInfo, node: 'AgentNode', db: 'AsyncSession') -> ServerConfig:
        from app.models.agent_certificate import AgentCertificate
        from sqlalchemy import select, case
        from app.services.crypto_service import crypto_service
        
        # Priority: pending=0, active=1
        status_priority = case(
            (AgentCertificate.status == "pending", 0),
            (AgentCertificate.status == "active", 1),
            else_=2
        )
        
        # Get pending cert if exists, otherwise active
        result = await db.execute(
            select(AgentCertificate)
            .where(AgentCertificate.node_id == node.id)
            .where(AgentCertificate.status.in_(["pending", "active"]))
            .order_by(status_priority, AgentCertificate.rotation_version.desc())
        )
        cert = result.scalars().first()
        
        certificates_payload = []
        if cert:
            decrypted_pfx = crypto_service.decrypt_blob(
                key_version=cert.crypto_key_version,
                crypto_nonce=cert.crypto_nonce,
                crypto_tag=cert.crypto_tag,
                encrypted_blob=cert.encrypted_pfx
            )
            # Encode byte array as base64 string for JSON transmission
            # Wait, CertificateData in VPNHood uses byte[] which JSON serializes to base64.
            import base64
            certificates_payload.append({
                "CommonName": cert.common_name or "VPN Node",
                "RawData": base64.b64encode(decrypted_pfx).decode('ascii')
            })
            
        machine_name = server_info.machine_name or "unknown"
        logger.info(
            f"VPNHood node configure - "
            f"Machine: {machine_name}, "
            f"ConfigRev: {node.config_revision}, "
            f"Cert: {cert.rotation_version if cert else 'None'}"
        )
        
        return ServerConfig(
            configCode=str(node.config_revision),
            certificates=certificates_payload
        )

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

    async def update_status(self, status: ServerStatus, node: 'AgentNode', db: 'AsyncSession') -> ServerCommand:
        from app.models.agent_certificate import AgentCertificate
        from sqlalchemy import select, update
        
        # Two-phase certificate commit
        # If there's no config_error and we have a pending cert, promote it to active.
        if not status.config_error:
            # Promote pending to active, retire active
            result = await db.execute(
                select(AgentCertificate).where(AgentCertificate.node_id == node.id)
            )
            certs = result.scalars().all()
            
            pending_certs = [c for c in certs if c.status == "pending"]
            active_certs = [c for c in certs if c.status == "active"]
            
            if pending_certs:
                for c in active_certs:
                    c.status = "retired"
                for c in pending_certs:
                    c.status = "active"
                await db.commit()
                logger.info(f"Node {node.id} promoted pending certificate to active.")

        return ServerCommand(configCode=str(node.config_revision))
