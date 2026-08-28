from __future__ import annotations
from typing import Optional, Dict, List, Any
from enum import IntEnum, Enum
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime


class SessionErrorCode(str, Enum):
    Ok = "Ok"
    AccessError = "AccessError"
    PlanRejected = "PlanRejected"
    GeneralError = "GeneralError"
    SessionClosed = "SessionClosed"
    SessionSuppressedBy = "SessionSuppressedBy"
    SessionError = "SessionError"
    SessionExpired = "SessionExpired"
    AccessExpired = "AccessExpired"
    AccessCodeRejected = "AccessCodeRejected"
    AccessLocked = "AccessLocked"
    AccessTrafficOverflow = "AccessTrafficOverflow"
    DailyLimitExceeded = "DailyLimitExceeded"
    NoServerAvailable = "NoServerAvailable"
    PremiumLocation = "PremiumLocation"
    AdError = "AdError"
    RewardedAdRejected = "RewardedAdRejected"
    Maintenance = "Maintenance"


class SessionSuppressType(str, Enum):
    None_ = "None"
    YourSelf = "YourSelf"
    Other = "Other"


class AdRequirement(str, Enum):
    None_ = "None"
    Flexible = "Flexible"
    Rewarded = "Rewarded"


class ClientInfo(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    client_id: str = Field(..., alias="clientId")
    client_version: str = Field(..., alias="clientVersion")
    min_protocol_version: int = Field(..., alias="minProtocolVersion")
    max_protocol_version: int = Field(..., alias="maxProtocolVersion")
    user_agent: str = Field(..., alias="userAgent")


class UserReview(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    action: str = Field(..., alias="action")


class ConnectPlanId(str, Enum):
    Normal = "Normal"
    NormalByRewardedAd = "NormalByRewardedAd"
    PremiumByTrial = "PremiumByTrial"
    PremiumByRewardedAd = "PremiumByRewardedAd"
    Status = "Status"


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
    error_code: SessionErrorCode = Field(SessionErrorCode.Ok, alias="errorCode")
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


class ServerInfo(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    version: Optional[str] = Field(None)
    environment_version: Optional[str] = Field(None, alias="environmentVersion")
    private_ip_addresses: Optional[List[str]] = Field(None, alias="privateIpAddresses")
    public_ip_addresses: Optional[List[str]] = Field(None, alias="publicIpAddresses")
    status: Optional[ServerStatus] = Field(None)
    os_info: Optional[str] = Field(None, alias="osInfo")
    os_version: Optional[str] = Field(None, alias="osVersion")
    total_memory: Optional[int] = Field(None, alias="totalMemory")
    machine_name: Optional[str] = Field(None, alias="machineName")
    logical_core_count: Optional[int] = Field(None, alias="logicalCoreCount")
    free_udp_port_v4: Optional[int] = Field(None, alias="freeUdpPortV4")
    free_udp_port_v6: Optional[int] = Field(None, alias="freeUdpPortV6")
    free_quic_port_v4: Optional[int] = Field(None, alias="freeQuicPortV4")
    free_quic_port_v6: Optional[int] = Field(None, alias="freeQuicPortV6")
    network_interface_names: Optional[List[str]] = Field(None, alias="networkInterfaceNames")
    is_restarted: Optional[bool] = Field(None, alias="isRestarted")


class TrackingOptions(BaseModel):
    model_config = ConfigDict(populate_by_name=True)


class SessionOptions(BaseModel):
    model_config = ConfigDict(populate_by_name=True)


class NetFilterOptions(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

class CertificateData(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    common_name: str = Field(..., alias="commonName")
    raw_data: str = Field(..., alias="rawData")  # base64 encoded byte array

class ServerConfig(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    tracking_options: TrackingOptions = Field(default_factory=TrackingOptions, alias="Tracking")
    session_options: SessionOptions = Field(default_factory=SessionOptions, alias="Session")
    net_filter_options: NetFilterOptions = Field(default_factory=NetFilterOptions, alias="NetFilter")
    config_code: Optional[str] = Field(None, alias="configCode")
    certificates: Optional[List[CertificateData]] = Field(default=None, alias="certificates")
    tcp_endpoints: Optional[List[str]] = Field(default=None, alias="tcpEndPoints")
    udp_endpoints: Optional[List[str]] = Field(default=None, alias="udpEndPoints")
    update_status_interval: Optional[str] = Field(default=None, alias="updateStatusInterval")
    dns_servers: Optional[List[str]] = Field(default=None, alias="dnsServers")
