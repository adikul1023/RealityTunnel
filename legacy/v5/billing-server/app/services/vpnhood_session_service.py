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
                "common_name": cert.common_name or "VPN Node",
                "raw_data": base64.b64encode(decrypted_pfx).decode('ascii')
            })
            
        machine_name = server_info.machine_name or "unknown"
        # Phase 5F-A: log is_restarted prominently.
        # is_restarted=True means the VPNHood process just started; it does NOT mean
        # sessions are gone. RecoverSessions() already ran before Configure() is called,
        # so recovered sessions may be live in the node's memory by the time we see this.
        # No orphan cleanup is performed here. See Phase 5F-B for reconciliation design.
        logger.info(
            f"VPNHood node configure - "
            f"Machine: {machine_name}, "
            f"ConfigRev: {node.config_revision}, "
            f"Cert: {cert.rotation_version if cert else 'None'}, "
            f"IsRestarted: {server_info.is_restarted}"
        )
        
        import base64
        server_secret_b64 = base64.b64encode(node.id.bytes).decode('ascii')
        
        return ServerConfig(
            configCode=str(node.config_revision),
            certificates=certificates_payload,
            sync_interval="00:00:05",
            dns_servers=["8.8.8.8"],
            server_secret=server_secret_b64
        )

    async def create_session(self, request: SessionRequestEx, node: 'AgentNode', db: 'AsyncSession') -> SessionResponseEx:
        from app.models.agent_session import AgentSession
        
        logger.info(f"VPNHood Agent: Creating session for token {request.token_id}")
        
        if not request.token_id:
            return SessionResponseEx(
                errorCode=SessionErrorCode.Unauthorized,
                sessionId=0,
                sessionKey="",
                protocolVersion=request.protocol_version,
            )
            
        import random
        # Generate a 63-bit positive integer to fit safely in Postgres BIGINT and VPNHood ulong
        session_id = random.getrandbits(63)
        
        new_session = AgentSession(
            session_id=session_id,
            node_id=node.id,
            token_id=request.token_id,
            config_revision=node.config_revision,
            status="active"
        )
        db.add(new_session)
        await db.commit()
        
        response = SessionResponseEx(
            errorCode=SessionErrorCode.Ok,
            sessionId=session_id,
            sessionKey="ZHVtbXlfc2Vzc2lvbl9rZXk=", # Base64 encoded byte array in real impl
            protocolVersion=request.protocol_version,
            createdTime=datetime.now(timezone.utc)
        )
        return response

    async def get_session(self, session_id: int, node: 'AgentNode', db: 'AsyncSession') -> SessionResponseEx:
        logger.info(f"VPNHood Agent: Getting session {session_id}")
        return SessionResponseEx(
            errorCode=SessionErrorCode.Success,
            sessionId=session_id,
            sessionKey="",
            protocolVersion=0
        )

    async def get_all_sessions(self, node: 'AgentNode', db: 'AsyncSession') -> List[SessionResponseEx]:
        # Phase 5F-A: intentionally returns [] — session recovery is not implemented.
        #
        # VPNHood calls this endpoint (GET /api/agent/sessions) in RecoverSessions() on
        # startup. If we return active SessionResponseEx objects here, the node would
        # attempt to restore those sessions in memory. We do not yet return them because:
        #
        #   1. We have not traced exactly which fields VPNHood requires for a successful
        #      recovery (session key, virtual IP assignment, timestamps, etc.).
        #
        #   2. Even if the billing API were to return sessions, VPNHood also checks
        #      SessionLocalService (disk) before trusting the API response. The exact
        #      interaction between the two recovery paths is not yet verified.
        #
        # Current consequence: after a node restart without disk recovery, sessions that
        # were 'active' in the DB become orphans. This is operationally safe (orphaned
        # sessions generate no further usage events) but leaves stale metadata.
        #
        # Phase 5F-B will implement proper reconciliation: once get_all_sessions() returns
        # live sessions, a follow-up reconciliation step will close any DB sessions the
        # node failed to recover. The reconciliation trigger and required schema changes
        # will be determined after running the Recovery Matrix experiment.
        return []

    async def add_usage(self, session_id: int, traffic: Traffic, close_session: bool, node: 'AgentNode', db: 'AsyncSession') -> SessionResponse:
        from app.models.agent_session import AgentSession, SessionStatus
        from sqlalchemy import select

        # Fresh DB lookup — revocation must be authoritative from the database,
        # never from stale in-memory state.
        db_result = await db.execute(
            select(AgentSession).where(AgentSession.session_id == session_id)
        )
        session = db_result.scalar_one_or_none()

        if session is None:
            logger.warning(f"VPNHood Agent: add_usage for unknown session {session_id}")
            return SessionResponse(errorCode=SessionErrorCode.GeneralError)

        if session.status == SessionStatus.revoked:
            logger.info(f"VPNHood Agent: Revoking session {session_id} (AccessError returned to node)")
            return SessionResponse(errorCode=SessionErrorCode.AccessError)

        # Accumulate usage
        session.bytes_sent += traffic.sent
        session.bytes_received += traffic.received
        if close_session:
            session.status = SessionStatus.closed
            session.closed_at = __import__('datetime').datetime.now(__import__('datetime').timezone.utc)
        await db.commit()

        logger.info(f"VPNHood Agent: Adding usage to session {session_id} (close={close_session})")
        return SessionResponse(errorCode=SessionErrorCode.Ok)

    async def add_usages(self, usages: list[SessionUsage], node: 'AgentNode', db: 'AsyncSession') -> dict[str, SessionResponse]:
        from app.models.agent_session import AgentSession, SessionStatus
        from app.routers.agent_models import SessionResponse, SessionErrorCode
        from sqlalchemy import select
        
        result = {}
        for usage in usages:
            db_result = await db.execute(
                select(AgentSession).where(AgentSession.session_id == usage.session_id)
            )
            session = db_result.scalar_one_or_none()

            if session is None:
                result[str(usage.session_id)] = SessionResponse(errorCode=SessionErrorCode.GeneralError)
                continue

            # Fresh DB lookup — revocation is authoritative from the database.
            if session.status == SessionStatus.revoked:
                logger.info(f"VPNHood Agent: Revoking session {usage.session_id} via add_usages (AccessError)")
                result[str(usage.session_id)] = SessionResponse(errorCode=SessionErrorCode.AccessError)
                continue

            session.bytes_sent += usage.sent
            session.bytes_received += usage.received
            if usage.error_code == SessionErrorCode.SessionClosed.value:
                session.status = SessionStatus.closed
                session.closed_at = __import__('datetime').datetime.now(__import__('datetime').timezone.utc)

            result[str(usage.session_id)] = SessionResponse(errorCode=SessionErrorCode.Ok)

        await db.commit()
        return result

    async def update_status(self, status: ServerStatus, node: 'AgentNode', db: 'AsyncSession') -> ServerCommand:
        from app.models.agent_certificate import AgentCertificate
        from app.models.agent_session import AgentSession, SessionStatus
        from app.routers.agent_models import SessionResponse, SessionErrorCode
        from sqlalchemy import select, update
        import logging
        
        log = logging.getLogger("uvicorn")
        
        # Process usages embedded in status; build per-session responses for revocation signalling.
        session_responses: dict[str, SessionResponse] = {}
        if status.session_usages:
            for usage in status.session_usages:
                db_result = await db.execute(
                    select(AgentSession).where(AgentSession.session_id == usage.session_id)
                )
                session = db_result.scalar_one_or_none()

                if session is None:
                    session_responses[str(usage.session_id)] = SessionResponse(errorCode=SessionErrorCode.GeneralError)
                    continue

                # Fresh DB lookup — revocation is authoritative from the database.
                if session.status == SessionStatus.revoked:
                    log.info(f"VPNHood Agent: Revoking session {usage.session_id} via update_status (AccessError)")
                    session_responses[str(usage.session_id)] = SessionResponse(errorCode=SessionErrorCode.AccessError)
                    continue

                session.bytes_sent += usage.sent
                session.bytes_received += usage.received
                if usage.error_code == SessionErrorCode.SessionClosed.value:
                    session.status = SessionStatus.closed
                    session.closed_at = __import__('datetime').datetime.now(__import__('datetime').timezone.utc)

        # Touch AgentNode.updated_at to record this heartbeat for orphan cleanup logic
        node.updated_at = __import__('datetime').datetime.now(__import__('datetime').timezone.utc)

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

        # Proactive revocation scan: find ALL revoked sessions for this node,
        # regardless of whether VPNHood included them in this payload.
        # This is necessary because VPNHood only reports sessions with recent traffic;
        # zero-traffic sessions will never appear in status.session_usages, so we
        # must independently signal AccessError for any revoked session.
        revoked_result = await db.execute(
            select(AgentSession).where(
                AgentSession.node_id == node.id,
                AgentSession.status == SessionStatus.revoked
            )
        )
        revoked_sessions = revoked_result.scalars().all()
        for rev_session in revoked_sessions:
            sid_str = str(rev_session.session_id)
            if sid_str not in session_responses:
                log.info(
                    f"VPNHood Agent: Proactive revocation — signalling AccessError "
                    f"for session {rev_session.session_id} (no traffic in payload)"
                )
                session_responses[sid_str] = SessionResponse(errorCode=SessionErrorCode.AccessError)

        return ServerCommand(configCode=str(node.config_revision), sessionResponses=session_responses)

    @classmethod
    async def cleanup_orphaned_sessions(cls, db: 'AsyncSession') -> int:
        """
        Phase 5F-B: Conservative orphan cleanup policy.
        Closes 'active' sessions belonging to nodes that have not heartbeated for 24 hours.
        """
        from app.models.agent_session import AgentSession, SessionStatus
        from app.models.agent_node import AgentNode
        from sqlalchemy import update, select
        from datetime import datetime, timezone, timedelta
        import logging
        
        log = logging.getLogger(__name__)
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        
        # We find nodes that have not heartbeated (updated_at) in 24 hours
        # and update their sessions to 'closed'.
        stmt = (
            update(AgentSession)
            .where(AgentSession.status == SessionStatus.active)
            .where(
                AgentSession.node_id.in_(
                    select(AgentNode.id).where(AgentNode.updated_at < cutoff)
                )
            )
            .values(
                status=SessionStatus.closed,
                closed_at=datetime.now(timezone.utc)
            )
        )
        
        result = await db.execute(stmt)
        await db.commit()
        
        count = result.rowcount
        if count > 0:
            log.info(f"Phase 5F-B: Cleaned up {count} orphaned sessions from inactive nodes.")
            
        return count
