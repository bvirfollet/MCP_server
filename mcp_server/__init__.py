"""
Serveur MCP (Model Context Protocol)

Un serveur MCP sécurisé et modulaire en Python pur permettant aux modèles d'IA
(Claude, GPT, Gemini) d'interagir avec votre ordinateur de manière contrôlée.

CHANGELOG:
[2025-11-23 v0.1.0-alpha] Initial project setup
  - Project structure initialized
  - Core modules organized in layers
  - Security framework designed
  - Documentation completed

ARCHITECTURE:
- Layer 1 : Transport (Stdio, TCP, DBus)
- Layer 2 : Protocol & Routing (MCP Handler, Router)
- Layer 3 : Business Logic & Security (Auth, Permissions, Tools)
- Layer 4 : Resources (FileSystem, Execution, Sandbox)

SECURITY NOTES:
- All inputs validated strictly
- Deny by default authorization
- Complete audit logging
- Process isolation planned
- TLS 1.3 for network transports
"""

__version__ = "0.1.0-alpha"
__author__ = "MCP Development Team"
__license__ = "See LICENSE file"

# Version info
VERSION_MAJOR = 0
VERSION_MINOR = 1
VERSION_PATCH = 0
VERSION_SUFFIX = "alpha"

# Export main classes
from .core.mcp_server import MCPServer
from .transport.base_transport import BaseTransport
from .security.permission import Permission, PermissionType
from .tools.tool import Tool

__all__ = [
    "MCPServer",
    "BaseTransport",
    "Permission",
    "PermissionType",
    "Tool",
]
