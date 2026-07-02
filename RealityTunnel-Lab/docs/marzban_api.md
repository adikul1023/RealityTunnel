# Marzban API Reference

This document was generated from the live OpenAPI schema exposed by the running lab at `https://localhost:8000/openapi.json`.

Swagger UI is enabled in the lab at `https://localhost:8000/docs`.

## Global Notes

- `POST /api/admin/token` uses a form login flow and is the first call RealityTunnel will make to obtain a Marzban admin bearer token.
- Endpoints under `/sub/*` are subscription endpoints that Marzban serves for clients; RealityTunnel does not plan to rely on them.
- Response schemas below are shown as the first content schema Marzban publishes for each status code in the OpenAPI spec.

## Authentication

| Method | URL | Authentication required | Request body | Response | Purpose | RealityTunnel will use it |
|---|---|---|---|---|---|---|
| POST | /api/admin/token | No (form login) | application/x-www-form-urlencoded -> Body_admin_token_api_admin_token_post | 200 -> Token; 401 -> Unauthorized; 422 -> HTTPValidationError | Admin Token | Required |

## Administration

| Method | URL | Authentication required | Request body | Response | Purpose | RealityTunnel will use it |
|---|---|---|---|---|---|---|
| GET | /api/admin | Yes (Bearer admin token) | None | 200 -> Admin; 401 -> Unauthorized | Get Current Admin | Optional |
| POST | /api/admin | Yes (Bearer admin token) | application/json -> AdminCreate | 200 -> Admin; 401 -> Unauthorized; 403 -> Forbidden; 409 -> Conflict; 422 -> HTTPValidationError | Create Admin | Optional |
| DELETE | /api/admin/{username} | Yes (Bearer admin token) | None | 200 -> object; 401 -> Unauthorized; 403 -> Forbidden; 422 -> HTTPValidationError | Remove Admin | Optional |
| PUT | /api/admin/{username} | Yes (Bearer admin token) | application/json -> AdminModify | 200 -> Admin; 401 -> Unauthorized; 403 -> Forbidden; 422 -> HTTPValidationError | Modify Admin | Optional |
| POST | /api/admin/{username}/users/activate | Yes (Bearer admin token) | None | 200 -> object; 401 -> Unauthorized; 403 -> Forbidden; 404 -> NotFound; 422 -> HTTPValidationError | Activate All Disabled Users | Optional |
| POST | /api/admin/{username}/users/disable | Yes (Bearer admin token) | None | 200 -> object; 401 -> Unauthorized; 403 -> Forbidden; 404 -> NotFound; 422 -> HTTPValidationError | Disable All Active Users | Optional |
| GET | /api/admin/usage/{username} | Yes (Bearer admin token) | None | 200 -> integer; 401 -> Unauthorized; 403 -> Forbidden; 422 -> HTTPValidationError | Get Admin Usage | Optional |
| POST | /api/admin/usage/reset/{username} | Yes (Bearer admin token) | None | 200 -> Admin; 401 -> Unauthorized; 403 -> Forbidden; 422 -> HTTPValidationError | Reset Admin Usage | Optional |
| GET | /api/admins | Yes (Bearer admin token) | None | 200 -> array; 401 -> Unauthorized; 403 -> Forbidden; 422 -> HTTPValidationError | Get Admins | Optional |

## Users

| Method | URL | Authentication required | Request body | Response | Purpose | RealityTunnel will use it |
|---|---|---|---|---|---|---|
| POST | /api/user | Yes (Bearer admin token) | application/json -> UserCreate | 200 -> UserResponse; 400 -> HTTPException; 401 -> Unauthorized; 409 -> Conflict; 422 -> HTTPValidationError | Add User | Required |
| GET | /api/user_template | Yes (Bearer admin token) | None | 200 -> array; 422 -> HTTPValidationError | Get User Templates | Optional |
| POST | /api/user_template | Yes (Bearer admin token) | application/json -> UserTemplateCreate | 200 -> UserTemplateResponse; 422 -> HTTPValidationError | Add User Template | Optional |
| DELETE | /api/user_template/{template_id} | Yes (Bearer admin token) | None | 200 -> object; 422 -> HTTPValidationError | Remove User Template | Optional |
| GET | /api/user_template/{template_id} | Yes (Bearer admin token) | None | 200 -> UserTemplateResponse; 422 -> HTTPValidationError | Get User Template Endpoint | Optional |
| PUT | /api/user_template/{template_id} | Yes (Bearer admin token) | application/json -> UserTemplateModify | 200 -> UserTemplateResponse; 422 -> HTTPValidationError | Modify User Template | Optional |
| DELETE | /api/user/{username} | Yes (Bearer admin token) | None | 200 -> object; 401 -> Unauthorized; 403 -> Forbidden; 404 -> NotFound; 422 -> HTTPValidationError | Remove User | Required |
| GET | /api/user/{username} | Yes (Bearer admin token) | None | 200 -> UserResponse; 401 -> Unauthorized; 403 -> Forbidden; 404 -> NotFound; 422 -> HTTPValidationError | Get User | Required |
| PUT | /api/user/{username} | Yes (Bearer admin token) | application/json -> UserModify | 200 -> UserResponse; 400 -> HTTPException; 401 -> Unauthorized; 403 -> Forbidden; 404 -> NotFound; 422 -> HTTPValidationError | Modify User | Required |
| POST | /api/user/{username}/active-next | Yes (Bearer admin token) | None | 200 -> UserResponse; 401 -> Unauthorized; 403 -> Forbidden; 404 -> NotFound; 422 -> HTTPValidationError | Active Next Plan | Required |
| POST | /api/user/{username}/reset | Yes (Bearer admin token) | None | 200 -> UserResponse; 401 -> Unauthorized; 403 -> Forbidden; 404 -> NotFound; 422 -> HTTPValidationError | Reset User Data Usage | Required |
| POST | /api/user/{username}/revoke_sub | Yes (Bearer admin token) | None | 200 -> UserResponse; 401 -> Unauthorized; 403 -> Forbidden; 404 -> NotFound; 422 -> HTTPValidationError | Revoke User Subscription | Required |
| PUT | /api/user/{username}/set-owner | Yes (Bearer admin token) | None | 200 -> UserResponse; 401 -> Unauthorized; 422 -> HTTPValidationError | Set Owner | Required |
| GET | /api/user/{username}/usage | Yes (Bearer admin token) | None | 200 -> UserUsagesResponse; 401 -> Unauthorized; 403 -> Forbidden; 404 -> NotFound; 422 -> HTTPValidationError | Get User Usage | Required |

## Inbounds

| Method | URL | Authentication required | Request body | Response | Purpose | RealityTunnel will use it |
|---|---|---|---|---|---|---|
| GET | /api/inbounds | Yes (Bearer admin token) | None | 200 -> object; 401 -> Unauthorized | Get Inbounds | Required |

## Usage

| Method | URL | Authentication required | Request body | Response | Purpose | RealityTunnel will use it |
|---|---|---|---|---|---|---|
| GET | /api/users | Yes (Bearer admin token) | None | 200 -> UsersResponse; 400 -> HTTPException; 401 -> Unauthorized; 403 -> Forbidden; 404 -> NotFound; 422 -> HTTPValidationError | Get Users | Required |
| DELETE | /api/users/expired | Yes (Bearer admin token) | None | 200 -> array; 401 -> Unauthorized; 422 -> HTTPValidationError | Delete Expired Users | Required |
| GET | /api/users/expired | Yes (Bearer admin token) | None | 200 -> array; 401 -> Unauthorized; 422 -> HTTPValidationError | Get Expired Users | Required |
| POST | /api/users/reset | Yes (Bearer admin token) | None | 200 -> object; 401 -> Unauthorized; 403 -> Forbidden; 404 -> NotFound | Reset Users Data Usage | Required |
| GET | /api/users/usage | Yes (Bearer admin token) | None | 200 -> UsersUsagesResponse; 401 -> Unauthorized; 422 -> HTTPValidationError | Get Users Usage | Required |

## Nodes

| Method | URL | Authentication required | Request body | Response | Purpose | RealityTunnel will use it |
|---|---|---|---|---|---|---|
| POST | /api/node | Yes (Bearer admin token) | application/json -> NodeCreate | 200 -> NodeResponse; 401 -> Unauthorized; 403 -> Forbidden; 409 -> Conflict; 422 -> HTTPValidationError | Add Node | Optional |
| DELETE | /api/node/{node_id} | Yes (Bearer admin token) | None | 200 -> object; 401 -> Unauthorized; 403 -> Forbidden; 422 -> HTTPValidationError | Remove Node | Optional |
| GET | /api/node/{node_id} | Yes (Bearer admin token) | None | 200 -> NodeResponse; 401 -> Unauthorized; 403 -> Forbidden; 422 -> HTTPValidationError | Get Node | Optional |
| PUT | /api/node/{node_id} | Yes (Bearer admin token) | application/json -> NodeModify | 200 -> NodeResponse; 401 -> Unauthorized; 403 -> Forbidden; 422 -> HTTPValidationError | Modify Node | Optional |
| POST | /api/node/{node_id}/reconnect | Yes (Bearer admin token) | None | 200 -> object; 401 -> Unauthorized; 403 -> Forbidden; 422 -> HTTPValidationError | Reconnect Node | Optional |
| GET | /api/node/settings | Yes (Bearer admin token) | None | 200 -> NodeSettings; 401 -> Unauthorized; 403 -> Forbidden | Get Node Settings | Optional |
| GET | /api/nodes | Yes (Bearer admin token) | None | 200 -> array; 401 -> Unauthorized; 403 -> Forbidden | Get Nodes | Optional |
| GET | /api/nodes/usage | Yes (Bearer admin token) | None | 200 -> NodesUsageResponse; 401 -> Unauthorized; 403 -> Forbidden; 422 -> HTTPValidationError | Get Usage | Optional |

## System

| Method | URL | Authentication required | Request body | Response | Purpose | RealityTunnel will use it |
|---|---|---|---|---|---|---|
| GET | / | No | None | 200 -> object | Base | Optional |
| GET | /api/core | Yes (Bearer admin token) | None | 200 -> CoreStats; 401 -> Unauthorized | Get Core Stats | Optional |
| GET | /api/core/config | Yes (Bearer admin token) | None | 200 -> object; 401 -> Unauthorized; 403 -> Forbidden | Get Core Config | Optional |
| PUT | /api/core/config | Yes (Bearer admin token) | application/json -> object | 200 -> object; 401 -> Unauthorized; 403 -> Forbidden; 422 -> HTTPValidationError | Modify Core Config | Optional |
| POST | /api/core/restart | Yes (Bearer admin token) | None | 200 -> object; 401 -> Unauthorized; 403 -> Forbidden | Restart Core | Optional |
| GET | /api/hosts | Yes (Bearer admin token) | None | 200 -> object; 401 -> Unauthorized; 403 -> Forbidden | Get Hosts | Optional |
| PUT | /api/hosts | Yes (Bearer admin token) | application/json -> object | 200 -> object; 401 -> Unauthorized; 403 -> Forbidden; 422 -> HTTPValidationError | Modify Hosts | Optional |
| GET | /api/system | Yes (Bearer admin token) | None | 200 -> SystemStats; 401 -> Unauthorized | Get System Stats | Optional |

## Subscriptions

| Method | URL | Authentication required | Request body | Response | Purpose | RealityTunnel will use it |
|---|---|---|---|---|---|---|
| GET | /sub/{token}/ | No (subscription token is in the path) | None | 200 -> object; 422 -> HTTPValidationError | User Subscription | Unused |
| GET | /sub/{token}/{client_type} | No (subscription token is in the path) | None | 200 -> object; 422 -> HTTPValidationError | User Subscription With Client Type | Unused |
| GET | /sub/{token}/info | No (subscription token is in the path) | None | 200 -> SubscriptionUserResponse; 422 -> HTTPValidationError | User Subscription Info | Unused |
| GET | /sub/{token}/usage | No (subscription token is in the path) | None | 200 -> object; 422 -> HTTPValidationError | User Get Usage | Unused |

## RealityTunnel Endpoint Mapping

### Required

- POST /api/admin/token (Authentication)
- GET /api/inbounds (Inbounds)
- POST /api/user (Users)
- DELETE /api/user/{username} (Users)
- GET /api/user/{username} (Users)
- PUT /api/user/{username} (Users)
- POST /api/user/{username}/active-next (Users)
- POST /api/user/{username}/reset (Users)
- POST /api/user/{username}/revoke_sub (Users)
- PUT /api/user/{username}/set-owner (Users)
- GET /api/user/{username}/usage (Users)
- GET /api/users (Usage)
- DELETE /api/users/expired (Usage)
- GET /api/users/expired (Usage)
- POST /api/users/reset (Usage)
- GET /api/users/usage (Usage)

### Optional

- GET / (System)
- GET /api/admin (Administration)
- POST /api/admin (Administration)
- DELETE /api/admin/{username} (Administration)
- PUT /api/admin/{username} (Administration)
- POST /api/admin/{username}/users/activate (Administration)
- POST /api/admin/{username}/users/disable (Administration)
- GET /api/admin/usage/{username} (Administration)
- POST /api/admin/usage/reset/{username} (Administration)
- GET /api/admins (Administration)
- GET /api/core (System)
- GET /api/core/config (System)
- PUT /api/core/config (System)
- POST /api/core/restart (System)
- GET /api/hosts (System)
- PUT /api/hosts (System)
- POST /api/node (Nodes)
- DELETE /api/node/{node_id} (Nodes)
- GET /api/node/{node_id} (Nodes)
- PUT /api/node/{node_id} (Nodes)
- POST /api/node/{node_id}/reconnect (Nodes)
- GET /api/node/settings (Nodes)
- GET /api/nodes (Nodes)
- GET /api/nodes/usage (Nodes)
- GET /api/system (System)
- GET /api/user_template (Users)
- POST /api/user_template (Users)
- DELETE /api/user_template/{template_id} (Users)
- GET /api/user_template/{template_id} (Users)
- PUT /api/user_template/{template_id} (Users)

### Unused

- GET /sub/{token}/ (Subscriptions)
- GET /sub/{token}/{client_type} (Subscriptions)
- GET /sub/{token}/info (Subscriptions)
- GET /sub/{token}/usage (Subscriptions)

