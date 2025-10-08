"""
Authentication service for Keycloak integration.

Handles token verification, user authentication, and authorization
with Keycloak identity provider.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict

from app.core.config import settings
from fastapi import HTTPException, status
from jose import JWTError, jwt

logger = logging.getLogger(__name__)


class AuthService:
    """Service for handling authentication with Keycloak."""

    def __init__(self):
        """Initialize authentication service."""
        self.server_url = settings.keycloak_server_url
        self.realm = settings.keycloak_realm
        self.client_id = settings.keycloak_client_id
        self.verify_ssl = settings.keycloak_verify_ssl

        # Build Keycloak URLs
        self.realm_url = f"{self.server_url}/realms/{self.realm}"
        self.token_url = f"{self.realm_url}/protocol/openid-connect/token"
        self.userinfo_url = f"{self.realm_url}/protocol/openid-connect/userinfo"

    async def verify_token(self, token: str) -> Dict[str, Any]:
        """
        Verify JWT token and extract user information.

        Args:
            token: JWT access token from client

        Returns:
            Dict: User information containing sub, preferred_username, roles, etc.

        Raises:
            HTTPException: If token is invalid or verification fails
        """
        logger.debug("Starting token verification process")
        logger.debug(f"Token length: {len(token) if token else 0} characters")
        logger.debug(
            f"Token prefix: {token[:20] if token and len(token) > 20 else token}..."
        )

        try:
            # Decode token without verification first to get basic payload
            logger.debug("Decoding token without verification to extract claims")
            unverified_payload = jwt.get_unverified_claims(token)
            logger.debug(f"Unverified payload keys: {list(unverified_payload.keys())}")
            logger.debug(f"Token subject (sub): {unverified_payload.get('sub')}")
            logger.debug(f"Token issuer (iss): {unverified_payload.get('iss')}")
            logger.debug(f"Token audience (aud): {unverified_payload.get('aud')}")
            logger.debug(f"Token expiration (exp): {unverified_payload.get('exp')}")
            logger.debug(f"Token issued at (iat): {unverified_payload.get('iat')}")

            # Build expected issuer URL
            expected_issuer = f"{self.server_url}/realms/{self.realm}"
            logger.debug(f"Expected issuer: {expected_issuer}")

            # Verify token structure and basic claims
            logger.debug("Verifying token structure and basic claims")
            if not unverified_payload.get("sub"):
                logger.warning("Token verification failed: missing subject (sub) claim")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token: missing user ID",
                )
            logger.debug("✓ Subject (sub) claim present")

            # Check expiration manually
            logger.debug("Checking token expiration")
            exp = unverified_payload.get("exp")
            if exp:
                exp_datetime = datetime.fromtimestamp(exp, timezone.utc)
                current_time = datetime.now(timezone.utc)
                logger.debug(f"Token expires at: {exp_datetime}")
                logger.debug(f"Current time: {current_time}")
                logger.debug(f"Time until expiration: {exp_datetime - current_time}")

                if exp_datetime < current_time:
                    logger.warning(
                        f"Token verification failed: token expired at {exp_datetime}"
                    )
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Token has expired",
                    )
                logger.debug("✓ Token is not expired")
            else:
                logger.warning("Token has no expiration claim")

            # Check issuer
            logger.debug("Verifying token issuer")
            token_issuer = unverified_payload.get("iss")
            if token_issuer != expected_issuer:
                logger.warning(
                    f"Token verification failed: issuer mismatch. Expected: {expected_issuer}, Got: {token_issuer}"
                )
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token issuer",
                )
            logger.debug("✓ Token issuer is valid")

            # Check audience
            logger.debug("Verifying token audience")
            aud = unverified_payload.get("aud")
            logger.debug(f"Token audience: {aud}, Expected client ID: {self.client_id}")
            if aud:
                aud_list = aud if isinstance(aud, list) else [aud]
                if self.client_id not in aud_list:
                    logger.warning(
                        f"Token verification failed: audience mismatch. Expected: {self.client_id}, Got: {aud}"
                    )
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Invalid token audience",
                    )
                logger.debug("✓ Token audience is valid")
            else:
                logger.debug("No audience claim in token")

            # Extract user information
            logger.debug("Extracting user information from token")
            preferred_username = unverified_payload.get("preferred_username")
            email = unverified_payload.get("email")
            given_name = unverified_payload.get("given_name")
            family_name = unverified_payload.get("family_name")

            logger.debug(
                f"User details - Username: {preferred_username}, Email: {email}"
            )
            logger.debug(f"User name - Given: {given_name}, Family: {family_name}")

            roles = self._extract_roles(unverified_payload)
            logger.debug(f"Extracted roles: {roles}")

            user_info = {
                "sub": unverified_payload.get("sub"),
                "name": unverified_payload.get("name"),
                "preferred_username": preferred_username,
                "session_state": unverified_payload.get("session_state"),
                "given_name": given_name,
                "email": email,
                "family_name": family_name,
                "roles": roles,
                "exp": unverified_payload.get("exp"),
                "iat": unverified_payload.get("iat"),
            }

            logger.debug(
                f"✓ Token verification successful for user: {user_info['preferred_username']} (ID: {user_info['sub']})"
            )
            logger.debug(
                f"User has {len(roles)} roles: {', '.join(roles) if roles else 'none'}"
            )

            return user_info

        except HTTPException:
            raise
        except JWTError as e:
            logger.warning(f"Token verification failed with JWTError: {e}")
            logger.debug(f"JWT Error type: {type(e).__name__}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token",
            )
        except Exception as e:
            logger.exception(f"Unexpected error during token verification: {e}")
            logger.debug(f"Exception type: {type(e).__name__}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Authentication verification failed",
            )

    def _extract_roles(self, payload: Dict[str, Any]) -> list:
        """
        Extract roles from JWT payload.

        Args:
            payload: Decoded JWT payload

        Returns:
            List of user roles
        """
        roles = []

        # Extract realm roles
        realm_access = payload.get("realm_access", {})
        roles.extend(realm_access.get("roles", []))

        # Extract client roles
        resource_access = payload.get("resource_access", {})
        client_access = resource_access.get(self.client_id, {})
        roles.extend(client_access.get("roles", []))

        return list(set(roles))  # Remove duplicates

    async def get_user_info(self, token: str) -> Dict[str, Any]:
        """
        Retrieve user information from Keycloak using access token.

        Args:
            token: Valid JWT access token

        Returns:
            Dict containing user information

        Raises:
            HTTPException: If unable to retrieve user info
        """
        try:
            async with httpx.AsyncClient(verify=self.verify_ssl) as client:
                response = await client.get(
                    self.userinfo_url,
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=10.0,
                )
                response.raise_for_status()

                user_info = response.json()
                logger.debug(
                    f"Retrieved user info for: {user_info.get('preferred_username')}"
                )

                return user_info

        except httpx.HTTPError as e:
            logger.error(f"Failed to retrieve user info: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Unable to retrieve user information",
            )

    async def health_check(self) -> Dict[str, Any]:
        """
        Check health of Keycloak connection.

        Returns:
            Dict containing health status
        """
        try:
            async with httpx.AsyncClient(verify=self.verify_ssl) as client:
                response = await client.get(f"{self.realm_url}", timeout=5.0)
                response.raise_for_status()

                return {
                    "status": "healthy",
                    "keycloak_reachable": True,
                    "realm": self.realm,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
        except Exception as e:
            logger.error(f"Keycloak health check failed: {e}")
            return {
                "status": "unhealthy",
                "keycloak_reachable": False,
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
