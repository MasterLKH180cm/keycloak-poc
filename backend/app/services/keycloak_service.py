import logging
import time
from typing import Any, Dict, Optional

from app.core.config import settings
from jose import jwt
from keycloak import KeycloakAdmin, KeycloakOpenID
from keycloak.exceptions import KeycloakError

logger = logging.getLogger(__name__)


class KeycloakService:
    def __init__(self):
        self.admin_client: Optional[KeycloakAdmin] = None
        self.openid_client: Optional[KeycloakOpenID] = None

    async def init_keycloak(self):
        """Initialize Keycloak clients"""
        try:
            # Admin client for user management
            self.admin_client = KeycloakAdmin(
                server_url=settings.keycloak_server_url,
                username=settings.keycloak_admin_username,
                password=settings.keycloak_admin_password,
                realm_name=settings.keycloak_realm,
                verify=True,
            )

            # OpenID client for authentication
            self.openid_client = KeycloakOpenID(
                server_url=settings.keycloak_server_url,
                client_id=settings.keycloak_client_id,
                realm_name=settings.keycloak_realm,
                client_secret_key=settings.keycloak_client_secret,
                verify=True,
            )

            # Verify client configuration
            await self._verify_client_config()

            logger.info("Keycloak clients initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize Keycloak clients: {e}")
            raise

    async def _verify_client_config(self):
        """Verify that the client is properly configured"""
        try:
            # Try to get well-known configuration
            verify_admin_client = self.admin_client.verify
            logger.info(f"Keycloak admin_client verify {verify_admin_client}")
            well_known_openid_client = self.openid_client.well_known()
            logger.info(
                f"Keycloak openid_client well-known configuration retrieved successfully: {well_known_openid_client}"
            )
        except Exception as e:
            logger.warning(f"Could not retrieve well-known configuration: {e}")

    async def create_user(self, user_data: Dict[str, Any]) -> str:
        """Create user in Keycloak and return Keycloak user ID"""
        try:
            # Create user in Keycloak
            keycloak_id = self.admin_client.create_user(user_data)

            # Assign default role if specified
            user_role = user_data.get("attributes", {}).get("role", [])
            if user_role and len(user_role) > 0:
                await self._assign_user_role(keycloak_id, user_role[0])

            logger.info(f"User created in Keycloak with ID: {keycloak_id}")
            return keycloak_id

        except KeycloakError as e:
            logger.error(f"Keycloak error creating user: {e}")
            raise ValueError(f"Failed to create user in Keycloak: {e}")
        except Exception as e:
            logger.error(f"Unexpected error creating user: {e}")
            raise

    async def authenticate_user(self, username: str, password: str) -> Dict[str, Any]:
        """Authenticate user and return token information"""
        try:
            logger.info(f"Authenticating user: {username}")

            # Use signed JWT client authentication
            token = self.openid_client.token(
                username=username,
                password=password,
                grant_type="password",
                client_assertion_type=(
                    "urn:ietf:params:oauth:client-assertion-type:jwt-bearer"
                ),
                client_assertion=self._create_client_assertion(),
            )

            logger.info("Authentication successful")

            # Get user info from token
            userinfo = self.openid_client.userinfo(token["access_token"])

            return {
                "access_token": token["access_token"],
                "refresh_token": token["refresh_token"],
                "expires_in": token["expires_in"],
                "userinfo": userinfo,
            }

        except KeycloakError as e:
            error_msg = str(e)
            logger.error(f"Authentication failed for user {username}: {error_msg}")

            # Provide more specific error messages
            if "invalid_client" in error_msg:
                raise ValueError(
                    "Client configuration error. Please check Keycloak client settings."
                )
            elif "invalid_grant" in error_msg:
                raise ValueError("Invalid username or password")
            elif "unauthorized_client" in error_msg:
                raise ValueError("Client not authorized for this operation")
            else:
                raise ValueError(f"Authentication failed: {error_msg}")
        except Exception as e:
            logger.error(f"Unexpected error during authentication: {e}")
            raise

    async def refresh_token(self, refresh_token: str) -> Dict[str, Any]:
        """Refresh access token"""
        try:
            # Use Keycloak client token method with refresh_token grant type
            token = self.openid_client.token(
                grant_type="refresh_token",
                refresh_token=refresh_token,
                client_assertion_type="urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
                client_assertion=self._create_client_assertion(),
            )
            return token
        except KeycloakError as e:
            logger.error(f"Token refresh failed: {e}")
            raise ValueError("Invalid refresh token")
        except Exception as e:
            logger.error(f"Token refresh failed: {e}")
            raise ValueError("Invalid refresh token")

    async def logout_user(self, refresh_token: str):
        """Logout user by invalidating refresh token"""
        try:
            # Use token revocation to invalidate the refresh token
            import requests

            token_endpoint = (
                f"{settings.keycloak_server_url}/realms/"
                f"{settings.keycloak_realm}/protocol/openid-connect/logout"
            )

            data = {
                "client_id": settings.keycloak_client_id,
                "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
                "client_assertion": self._create_client_assertion(),
                "refresh_token": refresh_token,
            }

            response = requests.post(token_endpoint, data=data, verify=True)

            if response.status_code == 204:
                logger.info("User logged out successfully")
                return {"message": "Logout successful"}
            else:
                logger.error(f"Logout failed with status: {response.status_code}")
                raise ValueError("Logout failed")

        except KeycloakError as e:
            logger.error(f"Logout failed: {e}")
            raise ValueError("Logout failed")
        except Exception as e:
            logger.error(f"Unexpected error during logout: {e}")
            raise ValueError("Logout failed")

    async def get_user_info(self, user_id: str) -> Dict[str, Any]:
        """Get user details from Keycloak by user ID"""
        try:
            user = self.admin_client.get_user(user_id)
            return user
        except KeycloakError as e:
            logger.error(f"Failed to get user {user_id}: {e}")
            raise ValueError("User not found")

    async def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """Get user by username from Keycloak"""
        try:
            users = self.admin_client.get_users({"username": username})
            return users[0] if users else None
        except KeycloakError as e:
            logger.error(f"Failed to get user by username {username}: {e}")
            return None

    async def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Get user by email from Keycloak"""
        try:
            users = self.admin_client.get_users({"email": email})
            return users[0] if users else None
        except KeycloakError as e:
            logger.error(f"Failed to get user by email {email}: {e}")
            return None

    async def update_user(self, user_id: str, user_data: Dict[str, Any]):
        """Update user in Keycloak"""
        try:
            self.admin_client.update_user(user_id, user_data)
        except KeycloakError as e:
            logger.error(f"Failed to update user {user_id}: {e}")
            raise ValueError("Failed to update user")

    async def list_users(
        self, first: int = 0, max: int = 100, search: str = None, enabled: bool = None
    ) -> list:
        """List users from Keycloak with pagination"""
        try:
            query = {"first": first, "max": max}
            if search:
                query["search"] = search
            if enabled is not None:
                query["enabled"] = enabled

            users = self.admin_client.get_users(query=query)
            return users
        except KeycloakError as e:
            logger.error(f"Failed to list users: {e}")
            raise ValueError("Failed to list users")

    async def reset_user_password(
        self, user_id: str, password: str, temporary: bool = True
    ):
        """Reset user password in Keycloak"""
        try:
            self.admin_client.set_user_password(
                user_id=user_id, password=password, temporary=temporary
            )
        except KeycloakError as e:
            logger.error(f"Failed to reset password for user {user_id}: {e}")
            raise ValueError("Failed to reset password")

    async def delete_user(self, user_id: str):
        """Delete user from Keycloak"""
        try:
            self.admin_client.delete_user(user_id)
            logger.info(f"User {user_id} deleted from Keycloak")
        except KeycloakError as e:
            logger.error(f"Failed to delete user {user_id}: {e}")
            raise ValueError("Failed to delete user")

    def _create_client_assertion(self) -> str:
        """Create a JWT client assertion for authentication"""
        now = int(time.time())
        token_endpoint = (
            f"{settings.keycloak_server_url}/realms/"
            f"{settings.keycloak_realm}/protocol/openid-connect/token"
        )
        payload = {
            "iss": settings.keycloak_client_id,  # issuer
            "sub": settings.keycloak_client_id,  # subject
            "aud": token_endpoint,  # audience
            "exp": now + 300,  # expires in 5 minutes
            "iat": now,  # issued at
            "jti": f"{settings.keycloak_client_id}-{now}",  # unique identifier
        }

        return jwt.encode(payload, settings.keycloak_client_secret, algorithm="HS512")

    async def _assign_user_role(self, user_id: str, role: str):
        """Assign role to user"""
        try:
            # This is a simplified example - in production,
            # you'd have proper role mapping
            role_mapping = self.admin_client.get_realm_role(role)
            self.admin_client.assign_realm_roles(user_id, [role_mapping])
        except Exception as e:
            logger.warning(f"Failed to assign role {role} to user {user_id}: {e}")


# Global Keycloak service instance
keycloak_service = KeycloakService()
