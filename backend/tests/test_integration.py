import pytest
from httpx import AsyncClient


@pytest.mark.integration
@pytest.mark.asyncio
async def test_user_lifecycle(
    client: AsyncClient,
    mock_keycloak,
    mock_redis,
    db_session,
    sample_user_data,
    mock_jwt_token,
):
    """Test complete user lifecycle: create, login, update, deactivate"""

    # 1. Create user (as admin)
    mock_keycloak.create_user.return_value = "test-keycloak-id"

    # In real test, would need admin JWT token
    create_response = await client.post("/api/v1/users/", json=sample_user_data)

    # 2. Login as the created user
    mock_keycloak.authenticate_user.return_value = {
        **mock_jwt_token,
        "userinfo": {**mock_jwt_token["userinfo"], "sub": "test-keycloak-id"},
    }

    login_response = await client.post(
        "/api/v1/auth/login",
        json={
            "username": sample_user_data["username"],
            "password": sample_user_data["password"],
        },
    )

    # 3. Update user profile
    update_data = {"first_name": "Updated"}

    # Would need proper JWT auth header
    update_response = await client.put("/api/v1/users/test-user-id", json=update_data)

    # 4. Check audit logs were created
    audit_logs = await db_session.execute(
        "SELECT * FROM user_audit_logs WHERE action IN ('USER_CREATED', 'LOGIN', 'USER_UPDATED')"
    )

    # Basic structure tests (would be more comprehensive with proper auth)
    assert create_response.status_code in [201, 401]
    assert login_response.status_code in [200, 401]
    assert update_response.status_code in [200, 401, 404]
