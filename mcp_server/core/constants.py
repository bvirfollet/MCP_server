"""
Constants for MCP Server

Module: core.constants
Date: 2025-11-23
Version: 0.1.0-alpha

CHANGELOG:
[2025-11-23 v0.1.0-alpha] Initial constants definition
  - MCP protocol version constants
  - Server configuration defaults
  - Error codes and status codes
  - Security-related constants
  - Transport constants

SECURITY NOTES:
- All defaults are conservative (security-first)
- Timeouts configured to prevent DoS
- Message sizes limited
- Rate limiting prepared
"""

import json
from typing import Final

# ============================================================================
# MCP Protocol Constants
# ============================================================================

MCP_PROTOCOL_VERSION: Final[str] = "2024-11"
MCP_SPEC_URL: Final[str] = "https://modelcontextprotocol.io/spec/2024-11"

# Supported JSON-RPC version
JSONRPC_VERSION: Final[str] = "2.0"

# ============================================================================
# Server Configuration
# ============================================================================

# Server identity
SERVER_NAME: Final[str] = "MCPServer"
SERVER_VERSION: Final[str] = "0.1.0-alpha"
SERVER_DESCRIPTION: Final[str] = (
    "Secure MCP server for AI model integration with local system resources"
)

# Default timeouts (in seconds)
DEFAULT_REQUEST_TIMEOUT: Final[int] = 30
DEFAULT_HEALTH_CHECK_TIMEOUT: Final[int] = 5
DEFAULT_SHUTDOWN_TIMEOUT: Final[int] = 10

# Default limits
MAX_REQUEST_SIZE: Final[int] = 10 * 1024 * 1024  # 10 MB
MAX_RESPONSE_SIZE: Final[int] = 50 * 1024 * 1024  # 50 MB
MAX_CONCURRENT_REQUESTS: Final[int] = 100
MAX_MESSAGE_QUEUE_SIZE: Final[int] = 1000

# ============================================================================
# Transport Configuration
# ============================================================================

# Stdio transport
STDIO_BUFFER_SIZE: Final[int] = 4096
STDIO_ENCODING: Final[str] = "utf-8"

# TCP transport (future)
DEFAULT_TCP_PORT: Final[int] = 8080
DEFAULT_TCP_HOST: Final[str] = "127.0.0.1"
TCP_BACKLOG: Final[int] = 5

# ============================================================================
# MCP Messages - JSON-RPC Method Names
# ============================================================================

# Lifecycle methods
METHOD_INITIALIZE: Final[str] = "initialize"
METHOD_INITIALIZED: Final[str] = "initialized"
METHOD_SHUTDOWN: Final[str] = "shutdown"

# Tool methods
METHOD_TOOLS_LIST: Final[str] = "tools/list"
METHOD_TOOLS_CALL: Final[str] = "tools/call"

# Resource methods
METHOD_RESOURCES_LIST: Final[str] = "resources/list"
METHOD_RESOURCES_READ: Final[str] = "resources/read"

# Prompt methods
METHOD_PROMPTS_LIST: Final[str] = "prompts/list"
METHOD_PROMPTS_GET: Final[str] = "prompts/get"

# Completion methods
METHOD_COMPLETION_COMPLETE: Final[str] = "completion/complete"

# Logging methods
METHOD_LOGGING_SET_LEVEL: Final[str] = "logging/setLevel"

# ============================================================================
# Server Capabilities
# ============================================================================

DEFAULT_CAPABILITIES = {
    "tools": {
        "listChanged": False
    },
    "resources": {
        "subscribe": False,
        "listChanged": False
    },
    "prompts": {
        "listChanged": False
    }
}

# ============================================================================
# Error Codes (JSON-RPC Standard)
# ============================================================================

# JSON-RPC error codes
PARSE_ERROR: Final[int] = -32700
INVALID_REQUEST: Final[int] = -32600
METHOD_NOT_FOUND: Final[int] = -32601
INVALID_PARAMS: Final[int] = -32602
INTERNAL_ERROR: Final[int] = -32603
SERVER_ERROR_START: Final[int] = -32099
SERVER_ERROR_END: Final[int] = -32000

# Custom error codes
AUTHENTICATION_ERROR: Final[int] = -32100
AUTHORIZATION_ERROR: Final[int] = -32101
PERMISSION_DENIED: Final[int] = -32102
RESOURCE_NOT_FOUND: Final[int] = -32103
INVALID_STATE: Final[int] = -32104
EXECUTION_ERROR: Final[int] = -32105

# Error messages
ERROR_MESSAGES = {
    PARSE_ERROR: "Parse error",
    INVALID_REQUEST: "Invalid Request",
    METHOD_NOT_FOUND: "Method not found",
    INVALID_PARAMS: "Invalid params",
    INTERNAL_ERROR: "Internal error",
    AUTHENTICATION_ERROR: "Authentication failed",
    AUTHORIZATION_ERROR: "Authorization failed",
    PERMISSION_DENIED: "Permission denied",
    RESOURCE_NOT_FOUND: "Resource not found",
    INVALID_STATE: "Invalid state",
    EXECUTION_ERROR: "Execution error",
}

# ============================================================================
# Status Codes
# ============================================================================

STATUS_OK: Final[str] = "ok"
STATUS_ERROR: Final[str] = "error"
STATUS_UNAUTHORIZED: Final[str] = "unauthorized"
STATUS_FORBIDDEN: Final[str] = "forbidden"

# ============================================================================
# Security Constants
# ============================================================================

# Permission types
class PermissionType:
    """Permission type constants"""
    # File operations
    FILE_READ: Final[str] = "FILE_READ"
    FILE_WRITE: Final[str] = "FILE_WRITE"
    FILE_DELETE: Final[str] = "FILE_DELETE"
    FILE_WRITE_GLOBAL: Final[str] = "FILE_WRITE_GLOBAL"

    # Code execution
    CODE_EXECUTION: Final[str] = "CODE_EXECUTION"
    CODE_EXECUTION_SUDO: Final[str] = "CODE_EXECUTION_SUDO"

    # System commands
    SYSTEM_COMMAND: Final[str] = "SYSTEM_COMMAND"

    # Network
    NETWORK_OUTBOUND: Final[str] = "NETWORK_OUTBOUND"
    NETWORK_LISTEN: Final[str] = "NETWORK_LISTEN"

    # Process
    PROCESS_SPAWN: Final[str] = "PROCESS_SPAWN"
    PROCESS_KILL: Final[str] = "PROCESS_KILL"


# Default access levels
DEFAULT_ACCESS_LEVEL: Final[str] = "guest"

# Rate limiting defaults (requests per minute)
RATE_LIMIT_GUEST: Final[int] = 60
RATE_LIMIT_USER: Final[int] = 300
RATE_LIMIT_ADMIN: Final[int] = 1000

# ============================================================================
# Audit Logging
# ============================================================================

# Log levels
LOG_LEVEL_DEBUG: Final[str] = "DEBUG"
LOG_LEVEL_INFO: Final[str] = "INFO"
LOG_LEVEL_WARNING: Final[str] = "WARNING"
LOG_LEVEL_ERROR: Final[str] = "ERROR"
LOG_LEVEL_CRITICAL: Final[str] = "CRITICAL"

# Log formats
LOG_FORMAT_JSON: Final[str] = "json"
LOG_FORMAT_TEXT: Final[str] = "text"

# ============================================================================
# Default Configuration
# ============================================================================

# Build default configuration dict
def get_default_config() -> dict:
    """
    Get default server configuration

    Returns:
        dict: Default configuration
    """
    return {
        "server": {
            "name": SERVER_NAME,
            "version": SERVER_VERSION,
            "description": SERVER_DESCRIPTION,
        },
        "protocol": {
            "version": MCP_PROTOCOL_VERSION,
            "spec_url": MCP_SPEC_URL,
        },
        "timeouts": {
            "request": DEFAULT_REQUEST_TIMEOUT,
            "health_check": DEFAULT_HEALTH_CHECK_TIMEOUT,
            "shutdown": DEFAULT_SHUTDOWN_TIMEOUT,
        },
        "limits": {
            "max_request_size": MAX_REQUEST_SIZE,
            "max_response_size": MAX_RESPONSE_SIZE,
            "max_concurrent_requests": MAX_CONCURRENT_REQUESTS,
            "max_message_queue_size": MAX_MESSAGE_QUEUE_SIZE,
        },
        "transport": {
            "default": "stdio",
            "stdio": {
                "buffer_size": STDIO_BUFFER_SIZE,
                "encoding": STDIO_ENCODING,
            },
            "tcp": {
                "host": DEFAULT_TCP_HOST,
                "port": DEFAULT_TCP_PORT,
                "backlog": TCP_BACKLOG,
            },
        },
        "security": {
            "default_access_level": DEFAULT_ACCESS_LEVEL,
            "rate_limits": {
                "guest": RATE_LIMIT_GUEST,
                "user": RATE_LIMIT_USER,
                "admin": RATE_LIMIT_ADMIN,
            },
        },
        "logging": {
            "level": LOG_LEVEL_INFO,
            "format": LOG_FORMAT_JSON,
        },
    }


# Unit tests for constants
if __name__ == "__main__":
    import unittest

    class TestConstants(unittest.TestCase):
        """Test suite for constants module"""

        def test_mcp_protocol_version(self):
            """Test MCP protocol version is set"""
            self.assertEqual(MCP_PROTOCOL_VERSION, "2024-11")

        def test_server_version(self):
            """Test server version format"""
            self.assertIn("0.1.0", SERVER_VERSION)
            self.assertIn("alpha", SERVER_VERSION)

        def test_json_rpc_version(self):
            """Test JSON-RPC version"""
            self.assertEqual(JSONRPC_VERSION, "2.0")

        def test_error_codes_are_negative(self):
            """Test error codes are negative integers"""
            self.assertLess(PARSE_ERROR, 0)
            self.assertLess(INVALID_REQUEST, 0)
            self.assertLess(METHOD_NOT_FOUND, 0)

        def test_error_messages_complete(self):
            """Test error messages for standard codes"""
            self.assertIn(PARSE_ERROR, ERROR_MESSAGES)
            self.assertIn(INVALID_REQUEST, ERROR_MESSAGES)
            self.assertIn(INTERNAL_ERROR, ERROR_MESSAGES)

        def test_permission_types(self):
            """Test permission type constants are defined"""
            self.assertTrue(hasattr(PermissionType, "FILE_READ"))
            self.assertTrue(hasattr(PermissionType, "CODE_EXECUTION"))
            self.assertTrue(hasattr(PermissionType, "SYSTEM_COMMAND"))

        def test_default_config(self):
            """Test default configuration structure"""
            config = get_default_config()
            self.assertIn("server", config)
            self.assertIn("protocol", config)
            self.assertIn("timeouts", config)
            self.assertIn("limits", config)
            self.assertIn("security", config)

        def test_config_values_are_positive(self):
            """Test timeout and limit values are positive"""
            self.assertGreater(DEFAULT_REQUEST_TIMEOUT, 0)
            self.assertGreater(MAX_REQUEST_SIZE, 0)
            self.assertGreater(MAX_CONCURRENT_REQUESTS, 0)

        def test_method_names_are_strings(self):
            """Test method names are non-empty strings"""
            self.assertIsInstance(METHOD_INITIALIZE, str)
            self.assertGreater(len(METHOD_INITIALIZE), 0)
            self.assertIsInstance(METHOD_TOOLS_CALL, str)
            self.assertGreater(len(METHOD_TOOLS_CALL), 0)

    unittest.main()
