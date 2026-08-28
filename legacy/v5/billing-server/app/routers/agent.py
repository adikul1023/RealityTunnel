"""
agent.py - VPNHood Internal Management API (Phase 2)
Handles communication with VPNHood Server agents for session and status management.
"""

from typing import List, Dict, Optional, Any
from fastapi import APIRouter, Depends, Query, Path, Request, Response
from pydantic import BaseModel

from app.dependencies import verify_agent_node, get_vpnhood_session_service
from app.services.vpnhood_session_service import VPNHoodSessionService
from app.models.agent_node import AgentNode
from app.database import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from app.routers.agent_models import (
    SessionRequestEx,
    SessionResponseEx,
    SessionUsage,
    SessionResponse,
    ServerStatus,
    ServerCommand,
    Traffic,
    ServerInfo,
    ServerConfig
)

router = APIRouter(
    prefix="/api/agent",
    tags=["Agent"],
    dependencies=[],
    responses={
        401: {"description": "Invalid Agent Token"},
    }
)

@router.post("/sessions", response_model=SessionResponseEx)
async def create_session(
    request: SessionRequestEx,
    service: VPNHoodSessionService = Depends(get_vpnhood_session_service),
    node: AgentNode = Depends(verify_agent_node),
    db: AsyncSession = Depends(get_db)
):
    return await service.create_session(request, node, db)

@router.get("/sessions/{session_id}", response_model=SessionResponseEx)
async def get_session(
    session_id: int = Path(...),
    host_end_point: Optional[str] = Query(None, alias="hostEndPoint"),
    client_ip: Optional[str] = Query(None, alias="clientIp"),
    service: VPNHoodSessionService = Depends(get_vpnhood_session_service),
    node: AgentNode = Depends(verify_agent_node),
    db: AsyncSession = Depends(get_db)
):
    return await service.get_session(session_id, node, db)

@router.get("/sessions", response_model=List[SessionResponseEx])
async def get_all_sessions(
    service: VPNHoodSessionService = Depends(get_vpnhood_session_service),
    node: AgentNode = Depends(verify_agent_node),
    db: AsyncSession = Depends(get_db)
):
    return await service.get_all_sessions(node, db)

@router.post("/sessions/{session_id}/usage", response_model=SessionResponse)
async def add_usage(
    request: Request,
    traffic: Traffic,
    session_id: int = Path(...),
    ad_data: Optional[str] = Query(None, alias="adData"),
    close_session: bool = Query(False, alias="closeSession"),
    service: VPNHoodSessionService = Depends(get_vpnhood_session_service),
    node: AgentNode = Depends(verify_agent_node),
    db: AsyncSession = Depends(get_db)
):
    body = await request.body()
    import logging
    logging.getLogger("uvicorn").error(f"OBSERVED USAGE PAYLOAD for {session_id}: {body.decode('utf-8')}")
    return await service.add_usage(session_id, traffic, close_session, node, db)

@router.post("/sessions/usages", response_model=Dict[str, SessionResponse])
async def add_usages(
    usages: List[SessionUsage],
    service: VPNHoodSessionService = Depends(get_vpnhood_session_service),
    node: AgentNode = Depends(verify_agent_node),
    db: AsyncSession = Depends(get_db)
):
    import logging
    log = logging.getLogger("uvicorn")
    log.info(f"VPNHood Agent: Adding multiple usages ({len(usages)})")
    return await service.add_usages(usages, node, db)

@router.post("/status", response_model=ServerCommand)
async def update_status(
    status: ServerStatus,
    service: VPNHoodSessionService = Depends(get_vpnhood_session_service),
    node: AgentNode = Depends(verify_agent_node),
    db: AsyncSession = Depends(get_db)
):
    return await service.update_status(status, node, db)

@router.post("/configure", response_model=ServerConfig)
async def configure(
    server_info: ServerInfo,
    service: VPNHoodSessionService = Depends(get_vpnhood_session_service),
    node: AgentNode = Depends(verify_agent_node),
    db: AsyncSession = Depends(get_db)
):
    return await service.configure(server_info, node, db)
