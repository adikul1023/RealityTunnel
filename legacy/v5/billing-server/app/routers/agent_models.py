from __future__ import annotations
from typing import Optional, Dict, List, Any
from enum import IntEnum
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime


class SessionErrorCode(IntEnum):
    Success = 0
    Unauthorized = 1
    Maintenance = 2
    NotSupported = 3
    QuotaReached = 4
    SessionClosed = 5
    InvalidClientVersion = 6
    Timeout = 7
    GeneralError = 8


class SessionSuppressType(IntEnum):
    None_ = 0
    Client = 1
    Server = 2


class AdRequirement(IntEnum):
    None_ = 0
    Banner = 1
    Interstitial = 2
    Rewarded = 3


class ClientInfo(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    client_id: str = Field(..., alias="clientId")
    os_name: str = Field(..., alias="osName")
    os_version: str = Field(..., alias="osVersion")
    app_version: str = Field(..., alias="appVersion")
    build_number: int = Field(..., alias="buildNumber")


class UserReview(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    action: str = Field(..., alias="action")


class ConnectPlanId(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(..., alias="id")
    type: int = Field(..., alias="type")


class SessionRequestEx(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    token_id: str = Field(..., alias="tokenId")
    client_info: ClientInfo = Field(..., alias="clientInfo")
    encrypted_client_id: str = Field(..., alias="encryptedClientId")
    client_country: Optional[str] = Field(None, alias="clientCountry")
    extra_data: Optional[str] = Field(None, alias="extraData")
    server_location: Optional[str] = Field(None, alias="serverLocation")
    plan_id: Optional[ConnectPlanId] = Field(None, alias="planId")
    allow_redirect: bool = Field(True, alias="allowRedirect")
    is_ipv6_supported: Optional[bool] = Field(None, alias="isIpV6Supported")
    protocol_version: int = Field(..., alias="protocolVersion")
    access_code: Optional[str] = Field(None, alias="accessCode")
    user_review: Optional[UserReview] = Field(None, alias="userReview")
    host_end_point: str = Field(..., alias="hostEndPoint")
    remote_end_point: Optional[str] = Field(None, alias="remoteEndPoint")
    client_ip: Optional[str] = Field(None, alias="clientIp")


class AccessUsage(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    total_bytes: int = Field(0, alias="totalBytes")
    used_bytes: int = Field(0, alias="usedBytes")
    expires_at: Optional[datetime] = Field(None, alias="expiresAt")


class ServerToken(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    
    token: str = Field(..., alias="token")


class Traffic(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    sent: int = Field(0, alias="sent")
    received: int = Field(0, alias="received")


class SessionResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    error_code: SessionErrorCode = Field(..., alias="errorCode")
    error_message: Optional[str] = Field(None, alias="errorMessage")
    access_usage: Optional[AccessUsage] = Field(None, alias="accessUsage")
    suppressed_by: SessionSuppressType = Field(SessionSuppressType.None_, alias="suppressedBy")
    redirect_server_tokens: Optional[List[ServerToken]] = Field(None, alias="redirectServerTokens")
    access_key: Optional[str] = Field(None, alias="accessKey")
    client_country: Optional[str] = Field(None, alias="clientCountry")
    client_public_address: Optional[str] = Field(None, alias="clientPublicAddress")


class AccessInfo(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    pass


class SessionResponseEx(SessionResponse):
    protocol_version: int = Field(..., alias="protocolVersion")
    extra_data: Optional[str] = Field(None, alias="extraData")
    ga_measurement_id: Optional[str] = Field(None, alias="gaMeasurementId")
    created_time: Optional[datetime] = Field(None, alias="createdTime")
    session_id: int = Field(..., alias="sessionId")
    session_key: str = Field(..., alias="sessionKey")
    server_location: Optional[str] = Field(None, alias="serverLocation")
    server_tags: List[str] = Field(default_factory=list, alias="serverTags")
    access_info: Optional[AccessInfo] = Field(None, alias="accessInfo")
    ad_requirement: AdRequirement = Field(AdRequirement.None_, alias="adRequirement")
    suppressed_to: SessionSuppressType = Field(SessionSuppressType.None_, alias="suppressedTo")


class SessionUsage(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    session_id: int = Field(..., alias="sessionId")
    error_code: SessionErrorCode = Field(SessionErrorCode.Success, alias="errorCode")
    sent: int = Field(0, alias="sent")
    received: int = Field(0, alias="received")
    ad_data: Optional[str] = Field(None, alias="adData")


class ServerHostEndPointStatus(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    pass


class ServerStatus(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    session_count: int = Field(..., alias="sessionCount")
    tcp_connection_count: int = Field(..., alias="tcpConnectionCount")
    udp_connection_count: int = Field(..., alias="udpConnectionCount")
    available_memory: Optional[int] = Field(None, alias="availableMemory")
    total_swap_memory: Optional[int] = Field(None, alias="totalSwapMemory")
    available_swap_memory: Optional[int] = Field(None, alias="availableSwapMemory")
    tcp_congestion_control: Optional[str] = Field(None, alias="tcpCongestionControl")
    cpu_usage: Optional[int] = Field(None, alias="cpuUsage")
    used_memory: int = Field(..., alias="usedMemory")
    thread_count: int = Field(..., alias="threadCount")
    tunnel_speed: Traffic = Field(..., alias="tunnelSpeed")
    config_code: Optional[str] = Field(None, alias="configCode")
    config_error: Optional[str] = Field(None, alias="configError")
    end_point_statuses: Optional[List[ServerHostEndPointStatus]] = Field(None, alias="endPointStatuses")
    session_usages: List[SessionUsage] = Field(default_factory=list, alias="sessionUsages")


class ServerCommand(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    config_code: str = Field(..., alias="configCode")
    session_responses: Dict[str, SessionResponse] = Field(default_factory=dict, alias="sessionResponses")


