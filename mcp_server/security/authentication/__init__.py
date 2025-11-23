"""
Authentication module - JWT and credential management

Provides:
- JWTHandler: JWT generation and validation (HS256)
- ClientManager: Client credentials and metadata
- PasswordHelper: bcrypt password hashing
"""

from .jwt_handler import (
    JWTHandler,
    JWTError,
    JWTInvalidError,
    JWTExpiredError,
    JWTClaimError,
    TokenPair,
    JWTClaims,
)
from .client_manager import (
    ClientManager,
    ClientRecord,
    ClientError,
    ClientNotFoundError,
    ClientExistsError,
    AuthenticationError,
)

__all__ = [
    "JWTHandler",
    "JWTError",
    "JWTInvalidError",
    "JWTExpiredError",
    "JWTClaimError",
    "TokenPair",
    "JWTClaims",
    "ClientManager",
    "ClientRecord",
    "ClientError",
    "ClientNotFoundError",
    "ClientExistsError",
    "AuthenticationError",
]
