"""
JWT Handler - Gestion des JSON Web Tokens

Module: security.authentication.jwt_handler
Date: 2025-11-23
Version: 0.3.0-alpha

CHANGELOG:
[2025-11-23 v0.3.0-alpha] Initial implementation
  - JWT generation with HS256
  - JWT validation and claim extraction
  - Token expiration management
  - Refresh token support
  - Custom error handling

ARCHITECTURE:
JWTHandler provides:
  - Stateless authentication with JWT
  - HS256 (HMAC-SHA256) signature
  - Configurable expiration times
  - Claim validation and extraction
  - Refresh token generation

SECURITY NOTES:
- HS256 used for internal auth (not for external APIs)
- Secret key must be 32+ characters (entropy)
- Token expiration enforced strictly
- All times in UTC
- No token storage in JWT (refresh tokens separate)
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Any
from dataclasses import dataclass
import uuid

import jwt


class JWTError(Exception):
    """Base JWT error"""
    pass


class JWTInvalidError(JWTError):
    """JWT is invalid (malformed, bad signature)"""
    pass


class JWTExpiredError(JWTError):
    """JWT has expired"""
    pass


class JWTClaimError(JWTError):
    """JWT claim validation failed"""
    pass


@dataclass
class TokenPair:
    """Access and refresh token pair"""
    access_token: str
    refresh_token: str
    access_expires_at: datetime
    refresh_expires_at: datetime
    token_type: str = "Bearer"


@dataclass
class JWTClaims:
    """Extracted JWT claims"""
    sub: str              # Subject (client_id)
    username: str
    jti: str              # JWT ID (for revocation)
    iat: datetime         # Issued at
    exp: datetime         # Expiration
    roles: list = None


class JWTHandler:
    """
    Handles JWT generation, validation, and token management

    Uses HS256 (HMAC-SHA256) for signing. Tokens are stateless
    but can be revoked via blacklist (managed elsewhere).
    """

    def __init__(
        self,
        secret_key: str,
        algorithm: str = "HS256",
        access_token_expire_minutes: int = 60,
        refresh_token_expire_days: int = 7,
    ):
        """
        Initialize JWT handler

        Args:
            secret_key: Secret key for signing (32+ characters)
            algorithm: JWT algorithm (default HS256)
            access_token_expire_minutes: Access token TTL in minutes
            refresh_token_expire_days: Refresh token TTL in days

        Raises:
            ValueError: If secret_key too short
        """
        if len(secret_key) < 32:
            raise ValueError("Secret key must be at least 32 characters")

        self.logger = logging.getLogger("security.jwt_handler")
        self.secret_key = secret_key
        self.algorithm = algorithm
        self.access_token_expire = timedelta(minutes=access_token_expire_minutes)
        self.refresh_token_expire = timedelta(days=refresh_token_expire_days)

        self.logger.info(
            f"JWT Handler initialized (algo={algorithm}, "
            f"access_expires={access_token_expire_minutes}min, "
            f"refresh_expires={refresh_token_expire_days}d)"
        )

    def generate_tokens(
        self,
        client_id: str,
        username: str,
        roles: Optional[list] = None,
    ) -> TokenPair:
        """
        Generate access and refresh token pair

        Args:
            client_id: Client identifier (UUID)
            username: Username for logging/auditing
            roles: User roles (for future RBAC)

        Returns:
            TokenPair with both tokens and expiration times
        """
        if not client_id or not username:
            raise ValueError("client_id and username required")

        jti = str(uuid.uuid4())  # Unique token ID for revocation
        now = datetime.now(timezone.utc)

        # Access token
        access_exp = now + self.access_token_expire
        access_claims = {
            "sub": client_id,
            "username": username,
            "jti": jti,
            "iat": int(now.timestamp()),
            "exp": int(access_exp.timestamp()),
            "roles": roles or [],
            "token_type": "access",
        }

        access_token = jwt.encode(
            access_claims,
            self.secret_key,
            algorithm=self.algorithm,
        )

        # Refresh token
        refresh_jti = str(uuid.uuid4())
        refresh_exp = now + self.refresh_token_expire
        refresh_claims = {
            "sub": client_id,
            "username": username,
            "jti": refresh_jti,
            "iat": int(now.timestamp()),
            "exp": int(refresh_exp.timestamp()),
            "token_type": "refresh",
        }

        refresh_token = jwt.encode(
            refresh_claims,
            self.secret_key,
            algorithm=self.algorithm,
        )

        self.logger.info(
            f"Tokens generated for {username} (client_id={client_id[:8]}...)"
        )

        return TokenPair(
            access_token=access_token,
            refresh_token=refresh_token,
            access_expires_at=access_exp,
            refresh_expires_at=refresh_exp,
        )

    def verify(self, token: str) -> JWTClaims:
        """
        Verify JWT signature and extract claims

        Args:
            token: JWT token string

        Returns:
            JWTClaims with extracted data

        Raises:
            JWTInvalidError: If token invalid or bad signature
            JWTExpiredError: If token expired
            JWTClaimError: If required claims missing
        """
        if not token or not isinstance(token, str):
            raise JWTInvalidError("Token must be non-empty string")

        try:
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm],
            )
        except jwt.ExpiredSignatureError as e:
            raise JWTExpiredError(f"Token expired: {e}")
        except jwt.InvalidSignatureError as e:
            raise JWTInvalidError(f"Invalid signature: {e}")
        except jwt.DecodeError as e:
            raise JWTInvalidError(f"Decode error: {e}")
        except jwt.InvalidTokenError as e:
            raise JWTInvalidError(f"Invalid token: {e}")

        # Validate required claims
        required_claims = ["sub", "username", "jti", "iat", "exp"]
        for claim in required_claims:
            if claim not in payload:
                raise JWTClaimError(f"Missing claim: {claim}")

        # Extract and convert timestamps
        try:
            iat = datetime.fromtimestamp(payload["iat"], tz=timezone.utc)
            exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        except (ValueError, TypeError) as e:
            raise JWTClaimError(f"Invalid timestamp: {e}")

        return JWTClaims(
            sub=payload["sub"],
            username=payload["username"],
            jti=payload["jti"],
            iat=iat,
            exp=exp,
            roles=payload.get("roles", []),
        )

    def refresh_access_token(self, refresh_token: str) -> str:
        """
        Generate new access token from refresh token

        Args:
            refresh_token: Valid refresh token

        Returns:
            New access token (JWT string)

        Raises:
            JWTInvalidError: If refresh token invalid
            JWTExpiredError: If refresh token expired
            JWTClaimError: If not a refresh token
        """
        # Verify refresh token
        claims = self.verify(refresh_token)

        # Check token type
        payload = jwt.decode(
            refresh_token,
            self.secret_key,
            algorithms=[self.algorithm],
            options={"verify_signature": False},  # Already verified above
        )

        if payload.get("token_type") != "refresh":
            raise JWTClaimError("Not a refresh token")

        # Generate new access token
        now = datetime.now(timezone.utc)
        access_exp = now + self.access_token_expire

        access_claims = {
            "sub": claims.sub,
            "username": claims.username,
            "jti": str(uuid.uuid4()),  # New JTI for new token
            "iat": int(now.timestamp()),
            "exp": int(access_exp.timestamp()),
            "roles": claims.roles,
            "token_type": "access",
        }

        access_token = jwt.encode(
            access_claims,
            self.secret_key,
            algorithm=self.algorithm,
        )

        self.logger.info(
            f"Access token refreshed for {claims.username}"
        )

        return access_token

    def decode_unverified(self, token: str) -> Dict[str, Any]:
        """
        Decode token WITHOUT verification (use with caution!)

        Useful for extracting claims to check expiration before
        verifying signature. Should only be used for non-security-critical
        purposes.

        Args:
            token: JWT token string

        Returns:
            Decoded payload dict

        Raises:
            JWTInvalidError: If token malformed
        """
        try:
            payload = jwt.decode(
                token,
                options={"verify_signature": False},
            )
            return payload
        except jwt.DecodeError as e:
            raise JWTInvalidError(f"Cannot decode token: {e}")


# ============================================================================
# Unit Tests
# ============================================================================

if __name__ == "__main__":
    import unittest
    import time

    class TestJWTHandler(unittest.TestCase):
        """Test suite for JWTHandler"""

        def setUp(self):
            """Setup before each test"""
            self.secret_key = "test-secret-key-at-least-32-characters-long!!!!"
            self.handler = JWTHandler(
                self.secret_key,
                access_token_expire_minutes=1,
                refresh_token_expire_days=7,
            )

        def test_initialization(self):
            """Test handler initialization"""
            self.assertEqual(self.handler.algorithm, "HS256")
            self.assertEqual(self.handler.secret_key, self.secret_key)

        def test_short_secret_key_raises(self):
            """Test short secret key rejected"""
            with self.assertRaises(ValueError):
                JWTHandler("short")

        def test_generate_tokens(self):
            """Test token generation"""
            client_id = "client-uuid-123"
            username = "alice"

            tokens = self.handler.generate_tokens(client_id, username)

            self.assertIsNotNone(tokens.access_token)
            self.assertIsNotNone(tokens.refresh_token)
            self.assertNotEqual(tokens.access_token, tokens.refresh_token)
            self.assertGreater(tokens.access_expires_at, datetime.now(timezone.utc))

        def test_verify_valid_token(self):
            """Test valid token verification"""
            client_id = "client-123"
            username = "bob"

            tokens = self.handler.generate_tokens(client_id, username)
            claims = self.handler.verify(tokens.access_token)

            self.assertEqual(claims.sub, client_id)
            self.assertEqual(claims.username, username)
            self.assertIsNotNone(claims.jti)

        def test_verify_invalid_signature(self):
            """Test invalid signature rejected"""
            client_id = "client-123"
            tokens = self.handler.generate_tokens(client_id, "alice")

            # Tamper with token
            bad_token = tokens.access_token[:-10] + "TAMPERED!!"

            with self.assertRaises(JWTInvalidError):
                self.handler.verify(bad_token)

        def test_verify_expired_token(self):
            """Test expired token rejected"""
            # Create handler with 0-second expiration
            handler = JWTHandler(
                self.secret_key,
                access_token_expire_minutes=0,
            )

            tokens = handler.generate_tokens("client", "alice")
            time.sleep(1)  # Wait for token to expire

            with self.assertRaises(JWTExpiredError):
                handler.verify(tokens.access_token)

        def test_verify_missing_claims(self):
            """Test missing required claims rejected"""
            # Create token without required claims
            payload = {"sub": "test"}  # Missing other claims

            bad_token = jwt.encode(
                payload,
                self.secret_key,
                algorithm="HS256",
            )

            with self.assertRaises(JWTClaimError):
                self.handler.verify(bad_token)

        def test_refresh_access_token(self):
            """Test access token refresh"""
            tokens = self.handler.generate_tokens("client", "alice")

            new_access = self.handler.refresh_access_token(tokens.refresh_token)

            self.assertIsNotNone(new_access)
            self.assertNotEqual(new_access, tokens.access_token)

            # Verify new token is valid
            claims = self.handler.verify(new_access)
            self.assertEqual(claims.username, "alice")

        def test_refresh_with_access_token_fails(self):
            """Test cannot refresh with access token"""
            tokens = self.handler.generate_tokens("client", "alice")

            # Try to refresh with access token (should fail)
            with self.assertRaises(JWTClaimError):
                self.handler.refresh_access_token(tokens.access_token)

        def test_decode_unverified(self):
            """Test unverified decode (no signature check)"""
            tokens = self.handler.generate_tokens("client", "alice")

            payload = self.handler.decode_unverified(tokens.access_token)

            self.assertEqual(payload["username"], "alice")
            self.assertEqual(payload["sub"], "client")

        def test_token_expiration_times(self):
            """Test expiration times are correct"""
            before = datetime.now(timezone.utc)
            tokens = self.handler.generate_tokens("client", "alice")
            after = datetime.now(timezone.utc)

            # Access token should expire in ~1 minute
            exp_diff = (tokens.access_expires_at - before).total_seconds()
            self.assertGreater(exp_diff, 59)  # At least 59 seconds
            self.assertLess(exp_diff, 61)     # At most 61 seconds

            # Refresh token should expire in ~7 days
            ref_diff = (tokens.refresh_expires_at - before).total_seconds()
            expected_seconds = 7 * 24 * 60 * 60  # 7 days
            self.assertGreater(ref_diff, expected_seconds - 10)
            self.assertLess(ref_diff, expected_seconds + 10)

        def test_roles_in_claims(self):
            """Test roles are preserved in claims"""
            roles = ["admin", "user"]
            tokens = self.handler.generate_tokens(
                "client", "alice", roles=roles
            )

            claims = self.handler.verify(tokens.access_token)
            self.assertEqual(claims.roles, roles)

    unittest.main()
