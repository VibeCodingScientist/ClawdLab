"""Security REST API Endpoints."""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Header, Query, status
from pydantic import BaseModel, EmailStr, Field

from platform.security.base import AuditAction, AuditResult, UserStatus
from platform.security.service import get_security_service


router = APIRouter(prefix="/security", tags=["security"])


# ===========================================
# REQUEST/RESPONSE MODELS
# ===========================================


class LoginRequest(BaseModel):
    """Login request."""

    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)
    ip_address: str = ""
    user_agent: str = ""


class LoginResponse(BaseModel):
    """Login response."""

    success: bool
    message: str
    access_token: str | None = None
    refresh_token: str | None = None
    session_id: str | None = None
    user: dict[str, Any] | None = None
    expires_at: str | None = None


class RefreshTokenRequest(BaseModel):
    """Token refresh request."""

    refresh_token: str


class RefreshTokenResponse(BaseModel):
    """Token refresh response."""

    success: bool
    message: str
    access_token: str | None = None
    expires_at: str | None = None


class CreateUserRequest(BaseModel):
    """Create user request."""

    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=8)
    roles: list[str] = Field(default_factory=lambda: ["viewer"])


class UpdateUserRequest(BaseModel):
    """Update user request."""

    username: str | None = None
    email: EmailStr | None = None
    status: str | None = None
    roles: list[str] | None = None
    permissions: list[str] | None = None
    metadata: dict[str, Any] | None = None


class ChangePasswordRequest(BaseModel):
    """Change password request."""

    current_password: str
    new_password: str = Field(..., min_length=8)


class UserResponse(BaseModel):
    """User response."""

    user_id: str
    username: str
    email: str
    status: str
    roles: list[str]
    permissions: list[str]
    created_at: str
    last_login: str | None


class CreateRoleRequest(BaseModel):
    """Create role request."""

    name: str = Field(..., min_length=2, max_length=50)
    description: str = ""
    permissions: list[str] = Field(default_factory=list)


class UpdateRoleRequest(BaseModel):
    """Update role request."""

    name: str | None = None
    description: str | None = None
    permissions: list[str] | None = None


class RoleResponse(BaseModel):
    """Role response."""

    role_id: str
    name: str
    description: str
    permissions: list[str]
    is_system: bool
    created_at: str


class CreatePolicyRequest(BaseModel):
    """Create policy request."""

    name: str = Field(..., min_length=2, max_length=100)
    description: str = ""
    effect: str = Field(..., pattern="^(allow|deny)$")
    principals: list[str]
    resources: list[str]
    actions: list[str]
    conditions: dict[str, Any] = Field(default_factory=dict)
    priority: int = 0


class UpdatePolicyRequest(BaseModel):
    """Update policy request."""

    name: str | None = None
    description: str | None = None
    effect: str | None = None
    principals: list[str] | None = None
    resources: list[str] | None = None
    actions: list[str] | None = None
    conditions: dict[str, Any] | None = None
    priority: int | None = None
    enabled: bool | None = None


class PolicyResponse(BaseModel):
    """Policy response."""

    policy_id: str
    name: str
    description: str
    effect: str
    principals: list[str]
    resources: list[str]
    actions: list[str]
    conditions: dict[str, Any]
    priority: int
    enabled: bool
    created_at: str


class CreateAPIKeyRequest(BaseModel):
    """Create API key request."""

    name: str = Field(..., min_length=2, max_length=100)
    scopes: list[str] = Field(default_factory=list)
    expires_days: int | None = None
    rate_limit: int | None = None


class APIKeyResponse(BaseModel):
    """API key response."""

    key_id: str
    name: str
    key_prefix: str
    scopes: list[str]
    rate_limit: int | None
    created_at: str
    expires_at: str | None
    last_used: str | None
    use_count: int
    active: bool


class APIKeyCreatedResponse(APIKeyResponse):
    """API key created response with raw key."""

    key_value: str  # Only returned on creation


class AuthorizeRequest(BaseModel):
    """Authorization check request."""

    resource: str
    action: str
    resource_id: str = ""
    context: dict[str, Any] = Field(default_factory=dict)


class AuthorizeResponse(BaseModel):
    """Authorization check response."""

    allowed: bool
    reason: str
    matched_policy: str
    matched_permission: str


class AuditQueryParams(BaseModel):
    """Audit log query parameters."""

    user_id: str | None = None
    username: str | None = None
    event_type: str | None = None
    action: str | None = None
    result: str | None = None
    resource_type: str | None = None
    resource_id: str | None = None
    ip_address: str | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    limit: int = 100
    offset: int = 0


class AuditEntryResponse(BaseModel):
    """Audit entry response."""

    entry_id: str
    event_type: str
    action: str
    result: str
    user_id: str
    username: str
    resource_type: str
    resource_id: str
    ip_address: str
    timestamp: str
    details: dict[str, Any]


class SessionResponse(BaseModel):
    """Session response."""

    session_id: str
    user_id: str
    ip_address: str
    user_agent: str
    created_at: str
    last_activity: str
    expires_at: str | None
    active: bool


# ===========================================
# AUTHENTICATION ENDPOINTS
# ===========================================


@router.post("/auth/login", response_model=LoginResponse)
async def login(request: LoginRequest) -> LoginResponse:
    """Authenticate user and create session."""
    service = get_security_service()

    result = await service.login(
        username=request.username,
        password=request.password,
        ip_address=request.ip_address,
        user_agent=request.user_agent,
    )

    if not result["success"]:
        return LoginResponse(
            success=False,
            message=result["error"],
        )

    return LoginResponse(
        success=True,
        message="Login successful",
        access_token=result["access_token"],
        refresh_token=result["refresh_token"],
        session_id=result["session_id"],
        user=result["user"].to_dict(),
        expires_at=result["expires_at"].isoformat(),
    )


@router.post("/auth/logout")
async def logout(
    session_id: str = Header(..., alias="X-Session-ID"),
) -> dict[str, Any]:
    """Logout and invalidate session."""
    service = get_security_service()

    success = await service.logout(session_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Session not found or already invalidated",
        )

    return {"success": True, "message": "Logged out successfully"}


@router.post("/auth/refresh", response_model=RefreshTokenResponse)
async def refresh_token(request: RefreshTokenRequest) -> RefreshTokenResponse:
    """Refresh access token."""
    service = get_security_service()

    token, error = await service._auth.refresh_access_token(request.refresh_token)

    if not token:
        return RefreshTokenResponse(
            success=False,
            message=error,
        )

    return RefreshTokenResponse(
        success=True,
        message="Token refreshed",
        access_token=token.token_value,
        expires_at=token.expires_at.isoformat() if token.expires_at else None,
    )


@router.post("/auth/verify")
async def verify_token(
    authorization: str = Header(..., alias="Authorization"),
) -> dict[str, Any]:
    """Verify a token and return user info."""
    service = get_security_service()

    # Extract token from Bearer header
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header",
        )

    token_value = authorization[7:]
    user, token, error = await service._auth.authenticate_token(token_value)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=error,
        )

    return {
        "valid": True,
        "user": user.to_dict(),
        "token": token.to_dict() if token else None,
    }


# ===========================================
# USER MANAGEMENT ENDPOINTS
# ===========================================


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(request: CreateUserRequest) -> UserResponse:
    """Create a new user."""
    service = get_security_service()

    try:
        user = await service.create_user(
            username=request.username,
            email=request.email,
            password=request.password,
            roles=request.roles,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    return UserResponse(
        user_id=user.user_id,
        username=user.username,
        email=user.email,
        status=user.status.value,
        roles=user.roles,
        permissions=user.permissions,
        created_at=user.created_at.isoformat(),
        last_login=user.last_login.isoformat() if user.last_login else None,
    )


@router.get("/users", response_model=list[UserResponse])
async def list_users(
    status_filter: str | None = Query(None, alias="status"),
    role: str | None = None,
) -> list[UserResponse]:
    """List all users."""
    service = get_security_service()

    user_status = UserStatus(status_filter) if status_filter else None
    users = await service._auth.list_users(status=user_status, role=role)

    return [
        UserResponse(
            user_id=u.user_id,
            username=u.username,
            email=u.email,
            status=u.status.value,
            roles=u.roles,
            permissions=u.permissions,
            created_at=u.created_at.isoformat(),
            last_login=u.last_login.isoformat() if u.last_login else None,
        )
        for u in users
    ]


@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(user_id: str) -> UserResponse:
    """Get a user by ID."""
    service = get_security_service()

    user = await service._auth.get_user(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return UserResponse(
        user_id=user.user_id,
        username=user.username,
        email=user.email,
        status=user.status.value,
        roles=user.roles,
        permissions=user.permissions,
        created_at=user.created_at.isoformat(),
        last_login=user.last_login.isoformat() if user.last_login else None,
    )


@router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(user_id: str, request: UpdateUserRequest) -> UserResponse:
    """Update a user."""
    service = get_security_service()

    updates = request.model_dump(exclude_none=True)
    user = await service.update_user(user_id, **updates)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return UserResponse(
        user_id=user.user_id,
        username=user.username,
        email=user.email,
        status=user.status.value,
        roles=user.roles,
        permissions=user.permissions,
        created_at=user.created_at.isoformat(),
        last_login=user.last_login.isoformat() if user.last_login else None,
    )


@router.delete("/users/{user_id}")
async def delete_user(user_id: str) -> dict[str, Any]:
    """Delete a user."""
    service = get_security_service()

    success = await service.delete_user(user_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return {"success": True, "message": "User deleted"}


@router.post("/users/{user_id}/change-password")
async def change_password(
    user_id: str,
    request: ChangePasswordRequest,
) -> dict[str, Any]:
    """Change user password."""
    service = get_security_service()

    try:
        success = await service._auth.change_password(
            user_id=user_id,
            current_password=request.current_password,
            new_password=request.new_password,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid current password",
        )

    return {"success": True, "message": "Password changed"}


@router.post("/users/{user_id}/roles/{role_name}")
async def assign_role(user_id: str, role_name: str) -> dict[str, Any]:
    """Assign a role to a user."""
    service = get_security_service()

    user = await service.assign_role(user_id, role_name)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return {"success": True, "message": f"Role '{role_name}' assigned", "roles": user.roles}


@router.delete("/users/{user_id}/roles/{role_name}")
async def remove_role(user_id: str, role_name: str) -> dict[str, Any]:
    """Remove a role from a user."""
    service = get_security_service()

    user = await service.remove_role(user_id, role_name)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return {"success": True, "message": f"Role '{role_name}' removed", "roles": user.roles}


# ===========================================
# ROLE MANAGEMENT ENDPOINTS
# ===========================================


@router.post("/roles", response_model=RoleResponse, status_code=status.HTTP_201_CREATED)
async def create_role(request: CreateRoleRequest) -> RoleResponse:
    """Create a new role."""
    service = get_security_service()

    try:
        role = await service.create_role(
            name=request.name,
            description=request.description,
            permissions=request.permissions,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    return RoleResponse(
        role_id=role.role_id,
        name=role.name,
        description=role.description,
        permissions=role.permissions,
        is_system=role.is_system,
        created_at=role.created_at.isoformat(),
    )


@router.get("/roles", response_model=list[RoleResponse])
async def list_roles() -> list[RoleResponse]:
    """List all roles."""
    service = get_security_service()

    roles = await service._authz.list_roles()

    return [
        RoleResponse(
            role_id=r.role_id,
            name=r.name,
            description=r.description,
            permissions=r.permissions,
            is_system=r.is_system,
            created_at=r.created_at.isoformat(),
        )
        for r in roles
    ]


@router.get("/roles/{role_id}", response_model=RoleResponse)
async def get_role(role_id: str) -> RoleResponse:
    """Get a role by ID."""
    service = get_security_service()

    role = await service._authz.get_role(role_id)
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found",
        )

    return RoleResponse(
        role_id=role.role_id,
        name=role.name,
        description=role.description,
        permissions=role.permissions,
        is_system=role.is_system,
        created_at=role.created_at.isoformat(),
    )


@router.put("/roles/{role_id}", response_model=RoleResponse)
async def update_role(role_id: str, request: UpdateRoleRequest) -> RoleResponse:
    """Update a role."""
    service = get_security_service()

    updates = request.model_dump(exclude_none=True)

    try:
        role = await service.update_role(role_id, **updates)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found",
        )

    return RoleResponse(
        role_id=role.role_id,
        name=role.name,
        description=role.description,
        permissions=role.permissions,
        is_system=role.is_system,
        created_at=role.created_at.isoformat(),
    )


@router.delete("/roles/{role_id}")
async def delete_role(role_id: str) -> dict[str, Any]:
    """Delete a role."""
    service = get_security_service()

    try:
        success = await service.delete_role(role_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found",
        )

    return {"success": True, "message": "Role deleted"}


# ===========================================
# POLICY MANAGEMENT ENDPOINTS
# ===========================================


@router.post("/policies", response_model=PolicyResponse, status_code=status.HTTP_201_CREATED)
async def create_policy(request: CreatePolicyRequest) -> PolicyResponse:
    """Create a new policy."""
    service = get_security_service()

    try:
        policy = await service.create_policy(
            name=request.name,
            description=request.description,
            effect=request.effect,
            principals=request.principals,
            resources=request.resources,
            actions=request.actions,
            conditions=request.conditions,
            priority=request.priority,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    return PolicyResponse(
        policy_id=policy.policy_id,
        name=policy.name,
        description=policy.description,
        effect=policy.effect,
        principals=policy.principals,
        resources=policy.resources,
        actions=policy.actions,
        conditions=policy.conditions,
        priority=policy.priority,
        enabled=policy.enabled,
        created_at=policy.created_at.isoformat(),
    )


@router.get("/policies", response_model=list[PolicyResponse])
async def list_policies() -> list[PolicyResponse]:
    """List all policies."""
    service = get_security_service()

    policies = await service._authz.list_policies()

    return [
        PolicyResponse(
            policy_id=p.policy_id,
            name=p.name,
            description=p.description,
            effect=p.effect,
            principals=p.principals,
            resources=p.resources,
            actions=p.actions,
            conditions=p.conditions,
            priority=p.priority,
            enabled=p.enabled,
            created_at=p.created_at.isoformat(),
        )
        for p in policies
    ]


@router.get("/policies/{policy_id}", response_model=PolicyResponse)
async def get_policy(policy_id: str) -> PolicyResponse:
    """Get a policy by ID."""
    service = get_security_service()

    policy = await service._authz.get_policy(policy_id)
    if not policy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Policy not found",
        )

    return PolicyResponse(
        policy_id=policy.policy_id,
        name=policy.name,
        description=policy.description,
        effect=policy.effect,
        principals=policy.principals,
        resources=policy.resources,
        actions=policy.actions,
        conditions=policy.conditions,
        priority=policy.priority,
        enabled=policy.enabled,
        created_at=policy.created_at.isoformat(),
    )


@router.put("/policies/{policy_id}", response_model=PolicyResponse)
async def update_policy(policy_id: str, request: UpdatePolicyRequest) -> PolicyResponse:
    """Update a policy."""
    service = get_security_service()

    updates = request.model_dump(exclude_none=True)
    policy = await service.update_policy(policy_id, **updates)

    if not policy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Policy not found",
        )

    return PolicyResponse(
        policy_id=policy.policy_id,
        name=policy.name,
        description=policy.description,
        effect=policy.effect,
        principals=policy.principals,
        resources=policy.resources,
        actions=policy.actions,
        conditions=policy.conditions,
        priority=policy.priority,
        enabled=policy.enabled,
        created_at=policy.created_at.isoformat(),
    )


@router.delete("/policies/{policy_id}")
async def delete_policy(policy_id: str) -> dict[str, Any]:
    """Delete a policy."""
    service = get_security_service()

    success = await service.delete_policy(policy_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Policy not found",
        )

    return {"success": True, "message": "Policy deleted"}


# ===========================================
# AUTHORIZATION ENDPOINTS
# ===========================================


@router.post("/authorize", response_model=AuthorizeResponse)
async def authorize(
    request: AuthorizeRequest,
    authorization: str = Header(..., alias="Authorization"),
) -> AuthorizeResponse:
    """Check if current user is authorized for an action."""
    service = get_security_service()

    # Extract token and get user
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header",
        )

    token_value = authorization[7:]
    user, _, error = await service._auth.authenticate_token(token_value)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=error,
        )

    result = await service.authorize(
        user=user,
        resource=request.resource,
        action=request.action,
        resource_id=request.resource_id,
        context=request.context,
    )

    return AuthorizeResponse(
        allowed=result.allowed,
        reason=result.reason,
        matched_policy=result.matched_policy,
        matched_permission=result.matched_permission,
    )


@router.get("/users/{user_id}/permissions")
async def get_user_permissions(user_id: str) -> dict[str, Any]:
    """Get all effective permissions for a user."""
    service = get_security_service()

    user = await service._auth.get_user(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    permissions = await service._authz.get_user_permissions(user)

    return {
        "user_id": user_id,
        "permissions": permissions,
    }


# ===========================================
# API KEY ENDPOINTS
# ===========================================


@router.post("/users/{user_id}/api-keys", response_model=APIKeyCreatedResponse, status_code=status.HTTP_201_CREATED)
async def create_api_key(user_id: str, request: CreateAPIKeyRequest) -> APIKeyCreatedResponse:
    """Create an API key for a user."""
    service = get_security_service()

    try:
        api_key, key_value = await service._auth.create_api_key(
            user_id=user_id,
            name=request.name,
            scopes=request.scopes,
            expires_days=request.expires_days,
            rate_limit=request.rate_limit,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    return APIKeyCreatedResponse(
        key_id=api_key.key_id,
        name=api_key.name,
        key_prefix=api_key.key_prefix,
        key_value=key_value,  # Only returned on creation!
        scopes=api_key.scopes,
        rate_limit=api_key.rate_limit,
        created_at=api_key.created_at.isoformat(),
        expires_at=api_key.expires_at.isoformat() if api_key.expires_at else None,
        last_used=None,
        use_count=0,
        active=True,
    )


@router.get("/users/{user_id}/api-keys", response_model=list[APIKeyResponse])
async def list_api_keys(user_id: str) -> list[APIKeyResponse]:
    """List API keys for a user."""
    service = get_security_service()

    keys = await service._auth.get_user_api_keys(user_id)

    return [
        APIKeyResponse(
            key_id=k.key_id,
            name=k.name,
            key_prefix=k.key_prefix,
            scopes=k.scopes,
            rate_limit=k.rate_limit,
            created_at=k.created_at.isoformat(),
            expires_at=k.expires_at.isoformat() if k.expires_at else None,
            last_used=k.last_used.isoformat() if k.last_used else None,
            use_count=k.use_count,
            active=k.active,
        )
        for k in keys
    ]


@router.delete("/api-keys/{key_id}")
async def revoke_api_key(key_id: str) -> dict[str, Any]:
    """Revoke an API key."""
    service = get_security_service()

    success = await service._auth.revoke_api_key(key_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found",
        )

    return {"success": True, "message": "API key revoked"}


# ===========================================
# SESSION ENDPOINTS
# ===========================================


@router.get("/users/{user_id}/sessions", response_model=list[SessionResponse])
async def list_user_sessions(user_id: str) -> list[SessionResponse]:
    """List active sessions for a user."""
    service = get_security_service()

    sessions = await service._auth.get_user_sessions(user_id)

    return [
        SessionResponse(
            session_id=s.session_id,
            user_id=s.user_id,
            ip_address=s.ip_address,
            user_agent=s.user_agent,
            created_at=s.created_at.isoformat(),
            last_activity=s.last_activity.isoformat(),
            expires_at=s.expires_at.isoformat() if s.expires_at else None,
            active=s.active,
        )
        for s in sessions
    ]


@router.delete("/sessions/{session_id}")
async def invalidate_session(session_id: str) -> dict[str, Any]:
    """Invalidate a specific session."""
    service = get_security_service()

    success = await service._auth.invalidate_session(session_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    return {"success": True, "message": "Session invalidated"}


@router.delete("/users/{user_id}/sessions")
async def invalidate_all_sessions(user_id: str) -> dict[str, Any]:
    """Invalidate all sessions for a user."""
    service = get_security_service()

    count = await service._auth.invalidate_all_user_sessions(user_id)

    return {"success": True, "message": f"{count} sessions invalidated"}


# ===========================================
# AUDIT LOG ENDPOINTS
# ===========================================


@router.get("/audit", response_model=list[AuditEntryResponse])
async def get_audit_entries(
    user_id: str | None = None,
    username: str | None = None,
    event_type: str | None = None,
    action: str | None = None,
    result: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    ip_address: str | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    limit: int = Query(100, le=1000),
    offset: int = Query(0, ge=0),
) -> list[AuditEntryResponse]:
    """Query audit log entries."""
    service = get_security_service()

    # Convert string params to enums if provided
    audit_action = AuditAction(action) if action else None
    audit_result = AuditResult(result) if result else None

    entries = await service._audit.get_entries(
        user_id=user_id,
        username=username,
        event_type=event_type,
        action=audit_action,
        result=audit_result,
        resource_type=resource_type,
        resource_id=resource_id,
        ip_address=ip_address,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
        offset=offset,
    )

    return [
        AuditEntryResponse(
            entry_id=e.entry_id,
            event_type=e.event_type,
            action=e.action.value,
            result=e.result.value,
            user_id=e.user_id,
            username=e.username,
            resource_type=e.resource_type,
            resource_id=e.resource_id,
            ip_address=e.ip_address,
            timestamp=e.timestamp.isoformat(),
            details=e.details,
        )
        for e in entries
    ]


@router.get("/audit/{entry_id}", response_model=AuditEntryResponse)
async def get_audit_entry(entry_id: str) -> AuditEntryResponse:
    """Get a specific audit entry."""
    service = get_security_service()

    entry = await service._audit.get_entry(entry_id)
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audit entry not found",
        )

    return AuditEntryResponse(
        entry_id=entry.entry_id,
        event_type=entry.event_type,
        action=entry.action.value,
        result=entry.result.value,
        user_id=entry.user_id,
        username=entry.username,
        resource_type=entry.resource_type,
        resource_id=entry.resource_id,
        ip_address=entry.ip_address,
        timestamp=entry.timestamp.isoformat(),
        details=entry.details,
    )


@router.get("/audit/users/{user_id}")
async def get_user_activity(
    user_id: str,
    days: int = Query(7, ge=1, le=90),
    limit: int = Query(100, le=1000),
) -> list[AuditEntryResponse]:
    """Get recent activity for a user."""
    service = get_security_service()

    entries = await service._audit.get_user_activity(
        user_id=user_id,
        days=days,
        limit=limit,
    )

    return [
        AuditEntryResponse(
            entry_id=e.entry_id,
            event_type=e.event_type,
            action=e.action.value,
            result=e.result.value,
            user_id=e.user_id,
            username=e.username,
            resource_type=e.resource_type,
            resource_id=e.resource_id,
            ip_address=e.ip_address,
            timestamp=e.timestamp.isoformat(),
            details=e.details,
        )
        for e in entries
    ]


@router.get("/audit/security-events")
async def get_security_events(
    days: int = Query(7, ge=1, le=90),
    limit: int = Query(100, le=1000),
) -> list[AuditEntryResponse]:
    """Get security-related events."""
    service = get_security_service()

    entries = await service._audit.get_security_events(days=days, limit=limit)

    return [
        AuditEntryResponse(
            entry_id=e.entry_id,
            event_type=e.event_type,
            action=e.action.value,
            result=e.result.value,
            user_id=e.user_id,
            username=e.username,
            resource_type=e.resource_type,
            resource_id=e.resource_id,
            ip_address=e.ip_address,
            timestamp=e.timestamp.isoformat(),
            details=e.details,
        )
        for e in entries
    ]


@router.get("/audit/stats")
async def get_audit_stats(
    start_time: datetime | None = None,
    end_time: datetime | None = None,
) -> dict[str, Any]:
    """Get audit statistics."""
    service = get_security_service()

    stats = await service._audit.get_stats(
        start_time=start_time,
        end_time=end_time,
    )

    return stats


@router.get("/audit/compliance-report")
async def generate_compliance_report(
    start_time: datetime,
    end_time: datetime,
) -> dict[str, Any]:
    """Generate a compliance report for a time period."""
    service = get_security_service()

    report = await service._audit.generate_compliance_report(
        start_time=start_time,
        end_time=end_time,
    )

    # Convert security events to serializable format
    report["security_events"] = [
        {
            "entry_id": e.entry_id,
            "event_type": e.event_type,
            "action": e.action.value,
            "result": e.result.value,
            "user_id": e.user_id,
            "username": e.username,
            "timestamp": e.timestamp.isoformat(),
        }
        for e in report["security_events"]
    ]

    return report


@router.get("/audit/export")
async def export_audit_entries(
    format: str = Query("json", pattern="^(json|csv)$"),
    start_time: datetime | None = None,
    end_time: datetime | None = None,
) -> dict[str, Any]:
    """Export audit entries."""
    service = get_security_service()

    data = await service._audit.export_entries(
        format=format,
        start_time=start_time,
        end_time=end_time,
    )

    return {
        "format": format,
        "data": data,
    }


__all__ = ["router"]
