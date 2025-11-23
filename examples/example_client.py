#!/usr/bin/env python3
"""
MCP Client Example - Démonstration Phase 2

Ce client MCP démontre les capacités Phase 2 :
- Enregistrement d'outils avec permissions
- Listage des outils disponibles
- Exécution sécurisée avec vérification des permissions
- Gestion des erreurs

Usage:
    # Démarrer le serveur dans un terminal:
    python -m mcp_server.server.example_server

    # Exécuter ce client dans un autre terminal:
    python examples/example_client.py
"""

import asyncio
import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp_server.transport.stdio_transport import StdioTransport
from mcp_server.protocol.mcp_protocol_handler import MCPProtocolHandler
from mcp_server.security.client_context import ClientContext
from mcp_server.core.mcp_server import MCPServer
from mcp_server.security.permission import Permission, PermissionType


class ExampleMCPClient:
    """Client MCP de démonstration Phase 2"""

    def __init__(self):
        """Initialiser le client"""
        self.server = None
        self.client_ctx = ClientContext()

    async def setup_server(self):
        """Configuration du serveur avec outils d'exemple"""
        self.server = MCPServer()

        # Enregistrer des outils d'exemple avec permissions

        @self.server.tool(
            name="greet",
            description="Salue un utilisateur par son nom",
            input_schema={
                "properties": {
                    "name": {"type": "string"},
                    "formal": {"type": "boolean"}
                },
                "required": ["name"]
            },
            permissions=[]  # Pas de permission requise
        )
        async def greet_tool(ctx, params):
            name = params.get("name", "World")
            formal = params.get("formal", False)

            if formal:
                greeting = f"Bonjour, {name}. Enchanté de vous rencontrer."
            else:
                greeting = f"Salut {name}! Ça va?"

            return {"greeting": greeting}

        @self.server.tool(
            name="read_status",
            description="Lit le statut d'un fichier",
            input_schema={
                "properties": {
                    "path": {"type": "string"}
                },
                "required": ["path"]
            },
            permissions=[Permission(PermissionType.FILE_READ, "/tmp/*")]
        )
        async def read_status(ctx, params):
            path = params.get("path", "/tmp/test")
            return {"status": f"File {path} is readable", "exists": True}

        @self.server.tool(
            name="execute_code",
            description="Exécute du code Python (restreint)",
            input_schema={
                "properties": {
                    "code": {"type": "string"}
                },
                "required": ["code"]
            },
            permissions=[
                Permission(PermissionType.CODE_EXECUTION, "restricted")
            ]
        )
        async def execute_code(ctx, params):
            code = params.get("code", "")
            # Simulation d'exécution sécurisée
            return {
                "output": f"Code executed: {code[:50]}...",
                "status": "success"
            }

        print("✓ Serveur configuré avec 3 outils d'exemple")
        print("  1. greet - Salutation (aucune permission)")
        print("  2. read_status - Lecture fichier (FILE_READ)")
        print("  3. execute_code - Exécution code (CODE_EXECUTION)")

    async def list_tools(self):
        """Récupérer la liste des outils disponibles"""
        print("\n" + "=" * 70)
        print("📋 LISTING DES OUTILS (tools/list)")
        print("=" * 70)

        tools = self.server.tool_manager.get_info_for_client(self.client_ctx)

        if not tools:
            print("❌ Aucun outil disponible")
            return

        for tool_info in tools:
            print(f"\n🔧 {tool_info['name']}")
            print(f"   Description: {tool_info['description']}")
            if 'input_schema' in tool_info:
                input_schema = tool_info['input_schema']
                if 'properties' in input_schema:
                    props = input_schema['properties']
                    print(f"   Paramètres: {', '.join(props.keys())}")
            if 'permissions' in tool_info:
                perms = tool_info['permissions']
                if perms:
                    print(f"   Permissions requises:")
                    for perm in perms:
                        print(f"     - {perm}")
                else:
                    print(f"   Permissions: Aucune")

    async def call_tool(self, tool_name: str, params: dict):
        """Appeler un outil en passant par le gestionnaire d'exécution"""
        print(f"\n" + "=" * 70)
        print(f"🚀 APPEL D'OUTIL: {tool_name}")
        print("=" * 70)

        # Initialiser les permissions du client
        self.server.permission_manager.initialize_client(self.client_ctx.client_id)

        try:
            # Récupérer l'outil
            tool = self.server.tool_manager.get(tool_name)
            if not tool:
                print(f"❌ Erreur: Outil '{tool_name}' non trouvé")
                return

            print(f"Paramètres: {json.dumps(params, indent=2)}")
            print(f"Sandbox client: {self.client_ctx.client_id}")

            # Exécuter via ExecutionManager
            result = await self.server.execution_manager.execute_tool(
                tool, self.client_ctx, params
            )

            print(f"✓ Succès!")
            if isinstance(result, dict):
                if "content" in result:
                    for item in result.get("content", []):
                        print(f"  Résultat: {item}")
                else:
                    print(f"  Résultat: {json.dumps(result, indent=2)}")
            else:
                print(f"  Résultat: {result}")

        except Exception as e:
            print(f"❌ Erreur lors de l'exécution: {type(e).__name__}")
            print(f"   {str(e)}")

    async def demonstrate_permissions(self):
        """Démonstration du système de permissions"""
        print("\n" + "=" * 70)
        print("🔐 DÉMONSTRATION DES PERMISSIONS")
        print("=" * 70)

        # Cas 1: Outil sans permission requise
        print("\n[1] Appel de 'greet' (pas de permission requise)")
        await self.call_tool("greet", {"name": "Alice"})

        # Cas 2: Outil avec permission mais sans autorisation
        print("\n[2] Appel de 'read_status' (FILE_READ non autorisé - devrait échouer)")
        print("    Client n'a pas la permission FILE_READ")
        await self.call_tool("read_status", {"path": "/tmp/test.txt"})

        # Cas 3: Accorder la permission et réessayer
        print("\n[3] Accordage de permission FILE_READ au client")
        self.server.permission_manager.grant_permission(
            self.client_ctx.client_id,
            Permission(PermissionType.FILE_READ, "/tmp/*")
        )
        print(f"   ✓ Permission accordée")

        print("\n[4] Nouvel appel de 'read_status' (devrait réussir)")
        await self.call_tool("read_status", {"path": "/tmp/test.txt"})

        # Cas 4: Outil de code execution
        print("\n[5] Appel de 'execute_code' (CODE_EXECUTION non autorisé)")
        print("    Client n'a pas la permission CODE_EXECUTION")
        await self.call_tool("execute_code", {"code": "print('Hello')"})

    async def show_audit_trail(self):
        """Afficher l'audit trail des exécutions"""
        print("\n" + "=" * 70)
        print("📜 AUDIT TRAIL")
        print("=" * 70)

        log = self.server.execution_manager.get_execution_log()

        if not log:
            print("Aucune exécution enregistrée")
            return

        for entry in log:
            print(f"\n{entry['timestamp']}")
            print(f"  Outil: {entry['tool_name']}")
            print(f"  Client: {entry['client_id']}")
            print(f"  Statut: {entry['status']}")
            print(f"  Durée: {entry['execution_time_ms']}ms")
            if "error" in entry:
                print(f"  Erreur: {entry['error']}")

    async def show_statistics(self):
        """Afficher les statistiques"""
        print("\n" + "=" * 70)
        print("📊 STATISTIQUES")
        print("=" * 70)

        stats = self.server.execution_manager.get_stats()
        print(f"Exécutions totales: {stats['total_executions']}")
        print(f"Succès: {stats['success_count']}")
        print(f"Erreurs: {stats['error_count']}")
        print(f"Taux de succès: {stats['success_rate']*100:.1f}%")
        print(f"Durée moyenne: {stats['avg_execution_time_ms']:.1f}ms")

        # Statut du client
        sandbox = self.server.execution_manager.get_sandbox(
            self.client_ctx.client_id
        )
        sandbox_stats = sandbox.get_stats()
        print(f"\nClient sandbox:")
        print(f"  Variable count: {sandbox_stats['variable_count']}")
        print(f"  Execution count: {sandbox_stats['execution_count']}")
        print(f"  Idle time: {sandbox_stats['idle_seconds']:.1f}s")

    async def run(self):
        """Exécuter la démonstration complète"""
        print("\n" + "=" * 70)
        print("🎯 DÉMONSTRATION CLIENT MCP - PHASE 2")
        print("=" * 70)
        print("\nFonctionnalités testées:")
        print("  ✓ Enregistrement d'outils avec décorateur")
        print("  ✓ Système RBAC (Permissions)")
        print("  ✓ Listage des outils")
        print("  ✓ Exécution sécurisée avec timeouts")
        print("  ✓ Audit trail complet")

        try:
            # Configuration
            await self.setup_server()

            # Listing
            await self.list_tools()

            # Démonstration permissions
            await self.demonstrate_permissions()

            # Audit trail
            await self.show_audit_trail()

            # Statistiques
            await self.show_statistics()

            print("\n" + "=" * 70)
            print("✓ DÉMONSTRATION TERMINÉE AVEC SUCCÈS")
            print("=" * 70)

        except Exception as e:
            print(f"\n❌ Erreur: {e}")
            import traceback
            traceback.print_exc()

async def main():
    """Point d'entrée principal"""
    client = ExampleMCPClient()
    await client.run()

if __name__ == "__main__":
    asyncio.run(main())
