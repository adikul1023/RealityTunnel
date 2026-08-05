"""
agent.py - VPNHood Internal Management API (Phase 2)
Handles communication with VPNHood Server agents for session and status management.
"""

from typing import List, Dict, Optional, Any
from fastapi import APIRouter, Depends, Query, Path, Request, Response
from pydantic import BaseModel

from app.dependencies import verify_agent_token, get_vpnhood_session_service
from app.services.vpnhood_session_service import VPNHoodSessionService
from app.routers.agent_models import (
    SessionRequestEx,
    SessionResponseEx,
    SessionUsage,
    SessionResponse,
    ServerStatus,
    ServerCommand,
    Traffic
)

router = APIRouter(
    prefix="/api/agent",
    tags=["Agent"],
    dependencies=[Depends(verify_agent_token)],
    responses={
        401: {"description": "Invalid Agent Token"},
    }
)


@router.post("/sessions", response_model=SessionResponseEx)
async def create_session(
    request: SessionRequestEx,
    service: VPNHoodSessionService = Depends(get_vpnhood_session_service)
):
    """Create a new VPNHood session from a token id"""
    return await service.create_session(request)


@router.get("/sessions/{session_id}", response_model=SessionResponseEx)
async def get_session(
    session_id: int = Path(...),
    host_end_point: Optional[str] = Query(None, alias="hostEndPoint"),
    client_ip: Optional[str] = Query(None, alias="clientIp"),
    service: VPNHoodSessionService = Depends(get_vpnhood_session_service)
):
    """Get the status of an existing session"""
    return await service.get_session(session_id)


@router.get("/sessions", response_model=List[SessionResponseEx])
async def get_all_sessions(
    service: VPNHoodSessionService = Depends(get_vpnhood_session_service)
):
    """Get all active sessions for this agent"""
    return await service.get_all_sessions()


@router.post("/sessions/{session_id}/usage", response_model=SessionResponse)
async def add_usage(
    traffic: Traffic,
    session_id: int = Path(...),
    ad_data: Optional[str] = Query(None, alias="adData"),
    close_session: bool = Query(False, alias="closeSession"),
    service: VPNHoodSessionService = Depends(get_vpnhood_session_service)
):
    """Add traffic usage to a session and optionally close it"""
    return await service.add_usage(session_id, traffic, close_session)


@router.post("/sessions/usages", response_model=Dict[str, SessionResponse])
async def add_usages(
    usages: List[SessionUsage],
    service: VPNHoodSessionService = Depends(get_vpnhood_session_service)
):
    """Bulk update usages for multiple sessions"""
    return await service.add_usages(usages)


@router.post("/status", response_model=ServerCommand)
async def update_status(
    status: ServerStatus,
    service: VPNHoodSessionService = Depends(get_vpnhood_session_service)
):
    """Update server telemetry and receive commands/config changes"""
    return await service.update_status(status)

