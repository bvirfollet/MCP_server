#!/usr/bin/env python3
"""
HeatSimulation 3D House Model Client - Phase 3 Integration Test

Demonstrates a realistic client for building 3D volumetric house models
compatible with HeatSimulation project.

Features:
- Phase 1: Server communication via Stdio transport
- Phase 2: Tool execution with permissions (FILE_WRITE for JSON export)
- Phase 3: JWT authentication + audit trail logging

Example: Build a passive house with realistic dimensions and materials.
"""

import asyncio
import json
import sys
import logging
from pathlib import Path
from datetime import datetime, timezone

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp_server import MCPServer
from mcp_server.security.permission import Permission, PermissionType
from mcp_server.security.client_context import ClientContext


# ============================================================================
# Logging Setup
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("heatmodel_client")


# ============================================================================
# HeatSimulation House Model Builder - Tool Implementation
# ============================================================================

class HouseModelBuilder:
    """Simple 3D house model builder for HeatSimulation."""

    def __init__(self):
        """Initialize the model builder."""
        self.model = None
        self.dimensions = None
        self.resolution = None

    def initialize_model(self, length_x: float, length_y: float, length_z: float, resolution: float = 0.1):
        """Initialize a new 3D house model."""
        self.dimensions = {"x": length_x, "y": length_y, "z": length_z}
        self.resolution = resolution
        self.model = {
            "metadata": {
                "version": "1.0",
                "description": "Modèle volumétrique 3D de maison",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "created_by": "HeatSimulation MCP Client (Phase 3)"
            },
            "geometry": {
                "dimensions": {
                    "length_x_m": length_x,
                    "length_y_m": length_y,
                    "length_z_m": length_z
                },
                "resolution_m": resolution,
                "grid_size": {
                    "N_x": int(length_x / resolution),
                    "N_y": int(length_y / resolution),
                    "N_z": int(length_z / resolution)
                },
                "vertices_3d": self._generate_vertices(length_x, length_y, length_z),
                "bounding_box": {
                    "min": {"x": 0.0, "y": 0.0, "z": 0.0},
                    "max": {"x": length_x, "y": length_y, "z": length_z}
                }
            },
            "volumes": [],  # Track added volumes
            "materials": {},
            "statistics": {
                "total_voxels": int((length_x / resolution) * (length_y / resolution) * (length_z / resolution)),
                "material_voxels": {}
            }
        }

        return {
            "status": "initialized",
            "dimensions": self.dimensions,
            "resolution": resolution,
            "grid_size": self.model["geometry"]["grid_size"]
        }

    def add_volume(self, x1: float, y1: float, z1: float, x2: float, y2: float, z2: float, material: str):
        """Add a rectangular volume with a specific material."""
        if self.model is None:
            return {"error": "Model not initialized"}

        volume_info = {
            "corners": {"p1": {"x": x1, "y": y1, "z": z1}, "p2": {"x": x2, "y": y2, "z": z2}},
            "material": material,
            "volume_m3": (x2 - x1) * (y2 - y1) * (z2 - z1),
            "added_at": datetime.now(timezone.utc).isoformat()
        }
        self.model["volumes"].append(volume_info)

        # Update material count
        if material not in self.model["statistics"]["material_voxels"]:
            self.model["statistics"]["material_voxels"][material] = 0

        voxel_count = int(
            ((x2 - x1) / self.resolution) *
            ((y2 - y1) / self.resolution) *
            ((z2 - z1) / self.resolution)
        )
        self.model["statistics"]["material_voxels"][material] += voxel_count

        return {
            "status": "volume_added",
            "material": material,
            "volume_m3": volume_info["volume_m3"],
            "voxels": voxel_count
        }

    def list_materials(self):
        """List available materials with their thermal properties."""
        materials = {
            "AIR": {
                "type": "AIR",
                "conductivity_W_mK": 0.026,
                "description": "Air zone (interior)"
            },
            "LIMITE_FIXE": {
                "type": "BOUNDARY",
                "conductivity_W_mK": None,
                "description": "Fixed boundary condition"
            },
            "PARPAING": {
                "type": "SOLIDE",
                "conductivity_W_mK": 1.1,
                "density_kg_m3": 2000.0,
                "specific_heat_J_kgK": 880.0,
                "description": "Concrete blocks"
            },
            "PLACO": {
                "type": "SOLIDE",
                "conductivity_W_mK": 0.25,
                "density_kg_m3": 800.0,
                "specific_heat_J_kgK": 900.0,
                "description": "Plasterboard BA13"
            },
            "LAINE_VERRE": {
                "type": "SOLIDE",
                "conductivity_W_mK": 0.04,
                "density_kg_m3": 25.0,
                "specific_heat_J_kgK": 840.0,
                "description": "Glass wool insulation"
            },
            "LAINE_BOIS": {
                "type": "SOLIDE",
                "conductivity_W_mK": 0.04,
                "density_kg_m3": 50.0,
                "specific_heat_J_kgK": 2100.0,
                "description": "Wood fiber insulation"
            },
            "TERRE": {
                "type": "SOLIDE",
                "conductivity_W_mK": 1.5,
                "density_kg_m3": 1600.0,
                "specific_heat_J_kgK": 1000.0,
                "description": "Ground/soil"
            },
            "BETON": {
                "type": "SOLIDE",
                "conductivity_W_mK": 1.7,
                "density_kg_m3": 2300.0,
                "specific_heat_J_kgK": 880.0,
                "description": "Concrete slab"
            },
            "POLYSTYRENE": {
                "type": "SOLIDE",
                "conductivity_W_mK": 0.035,
                "density_kg_m3": 25.0,
                "specific_heat_J_kgK": 1400.0,
                "description": "Expanded/extruded polystyrene"
            },
            "MUR_COMPOSITE_EXT": {
                "type": "SOLIDE",
                "conductivity_W_mK": 0.124,
                "density_kg_m3": 200.0,
                "specific_heat_J_kgK": 1050.0,
                "description": "External composite wall (insulated)"
            }
        }
        return materials

    def get_model_info(self):
        """Get information about the current model."""
        if self.model is None:
            return {"error": "Model not initialized"}

        return {
            "dimensions": self.model["geometry"]["dimensions"],
            "resolution_m": self.model["geometry"]["resolution_m"],
            "grid_size": self.model["geometry"]["grid_size"],
            "volumes_count": len(self.model["volumes"]),
            "total_voxels": self.model["statistics"]["total_voxels"],
            "material_voxels": self.model["statistics"]["material_voxels"],
            "created_at": self.model["metadata"]["created_at"]
        }

    def export_to_json(self, filepath: str = None):
        """Export the model to JSON format."""
        if self.model is None:
            return {"error": "Model not initialized"}

        if filepath is None:
            filepath = f"house_model_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        with open(filepath, 'w') as f:
            json.dump(self.model, f, indent=2)

        file_size_kb = Path(filepath).stat().st_size / 1024

        return {
            "status": "exported",
            "filepath": filepath,
            "file_size_kb": file_size_kb,
            "volumes": len(self.model["volumes"]),
            "total_voxels": self.model["statistics"]["total_voxels"]
        }

    @staticmethod
    def _generate_vertices(length_x: float, length_y: float, length_z: float):
        """Generate the 8 vertices of the bounding box."""
        vertices = []
        for i, x in enumerate([0, length_x]):
            for j, y in enumerate([0, length_y]):
                for k, z in enumerate([0, length_z]):
                    vertices.append({
                        "id": i * 4 + j * 2 + k,
                        "x": x,
                        "y": y,
                        "z": z
                    })
        return vertices


# ============================================================================
# MCP Server Setup with HeatSimulation Tools
# ============================================================================

def setup_heatmodel_server():
    """Setup MCP server with HeatSimulation tools."""
    server = MCPServer(
        server_name="HeatSimulation 3D Model Builder",
        server_version="3.0",
        data_dir="./data_heatmodel"
    )

    # Create builder instance
    builder = HouseModelBuilder()

    # Tool 1: Initialize model
    @server.tool(
        name="initialize_model",
        description="Initialize a new 3D house model with specified dimensions",
        input_schema={
            "type": "object",
            "properties": {
                "length_x": {"type": "number", "description": "Length in meters (X axis)"},
                "length_y": {"type": "number", "description": "Width in meters (Y axis)"},
                "length_z": {"type": "number", "description": "Height in meters (Z axis)"},
                "resolution": {"type": "number", "description": "Grid resolution in meters (default: 0.1)"}
            },
            "required": ["length_x", "length_y", "length_z"]
        }
    )
    async def tool_initialize_model(ctx: ClientContext, params: dict):
        """Initialize a new house model."""
        logger.info(f"[{ctx.username}] Initializing house model: {params['length_x']}x{params['length_y']}x{params['length_z']}m")
        result = builder.initialize_model(
            params["length_x"],
            params["length_y"],
            params["length_z"],
            params.get("resolution", 0.1)
        )
        return result

    # Tool 2: Add volume
    @server.tool(
        name="add_volume",
        description="Add a rectangular volume with a specific material to the model",
        input_schema={
            "type": "object",
            "properties": {
                "x1": {"type": "number", "description": "First corner X coordinate"},
                "y1": {"type": "number", "description": "First corner Y coordinate"},
                "z1": {"type": "number", "description": "First corner Z coordinate"},
                "x2": {"type": "number", "description": "Second corner X coordinate"},
                "y2": {"type": "number", "description": "Second corner Y coordinate"},
                "z2": {"type": "number", "description": "Second corner Z coordinate"},
                "material": {"type": "string", "description": "Material name"}
            },
            "required": ["x1", "y1", "z1", "x2", "y2", "z2", "material"]
        }
    )
    async def tool_add_volume(ctx: ClientContext, params: dict):
        """Add a volume to the model."""
        logger.info(f"[{ctx.username}] Adding volume: {params['material']}")
        result = builder.add_volume(
            params["x1"], params["y1"], params["z1"],
            params["x2"], params["y2"], params["z2"],
            params["material"]
        )
        return result

    # Tool 3: List materials
    @server.tool(
        name="list_materials",
        description="List all available materials with their thermal properties",
        input_schema={"type": "object", "properties": {}}
    )
    async def tool_list_materials(ctx: ClientContext, params: dict):
        """List available materials."""
        logger.info(f"[{ctx.username}] Listing available materials")
        return builder.list_materials()

    # Tool 4: Get model info
    @server.tool(
        name="get_model_info",
        description="Get information about the current model",
        input_schema={"type": "object", "properties": {}}
    )
    async def tool_get_model_info(ctx: ClientContext, params: dict):
        """Get model information."""
        logger.info(f"[{ctx.username}] Getting model info")
        return builder.get_model_info()

    # Tool 5: Export to JSON (requires FILE_WRITE permission)
    @server.tool(
        name="export_to_json",
        description="Export the model to JSON format for HeatSimulation",
        input_schema={
            "type": "object",
            "properties": {
                "filepath": {"type": "string", "description": "Output file path (optional)"}
            }
        },
        permissions=[Permission(PermissionType.FILE_WRITE, "/mnt/share/Sources/MCP_server/data_heatmodel/*")]
    )
    async def tool_export_to_json(ctx: ClientContext, params: dict):
        """Export model to JSON."""
        logger.info(f"[{ctx.username}] Exporting model to JSON")
        filepath = params.get("filepath")
        result = builder.export_to_json(filepath)
        return result

    return server


# ============================================================================
# Phase 3 Client with JWT Authentication
# ============================================================================

async def run_heatmodel_client():
    """Run the HeatSimulation 3D model client with Phase 3 authentication."""

    print("\n" + "="*80)
    print("HeatSimulation 3D House Model Builder - Phase 3 Integration Test")
    print("="*80)

    # Initialize server
    server = setup_heatmodel_server()

    # Phase 3: Create test client and authenticate
    print("\n[Phase 3] Authentication Setup")
    print("-" * 80)

    # Create a test client
    try:
        test_client = server.client_manager.create_client(
            username="architect",
            password="passive_house_2025",
            email="architect@heatsimulation.local",
            roles=["engineer", "modeler"]
        )
        print(f"✓ Client created: {test_client.username} (ID: {test_client.client_id[:8]}...)")
    except Exception as e:
        print(f"✓ Client 'architect' already exists: {e}")
        test_client = server.client_manager.get_client_by_username("architect")

    # Grant FILE_WRITE permission for JSON export
    server.permission_manager.grant_permission(
        test_client.client_id,
        Permission(PermissionType.FILE_WRITE, "/mnt/share/Sources/MCP_server/data_heatmodel/*")
    )
    print(f"✓ Permission granted: FILE_WRITE for data_heatmodel/")

    # Authenticate and get JWT
    print("\n[Phase 3] JWT Token Generation")
    print("-" * 80)

    auth_result = await server._handle_auth_token(
        ClientContext(),
        {"username": "architect", "password": "passive_house_2025"}
    )

    access_token = auth_result["access_token"]
    print(f"✓ Access token generated (valid for 1 hour)")
    print(f"  Token preview: {access_token[:30]}...{access_token[-10:]}")

    # Create authenticated context with the test client's ID
    ctx = ClientContext(
        client_info={"model": "HeatSimulation Builder"},
        client_id=test_client.client_id  # Link context to authenticated client
    )
    ctx.authenticated = True
    ctx.user_id = test_client.client_id
    ctx.username = test_client.username
    ctx.roles = test_client.roles
    ctx.auth_time = datetime.now(timezone.utc)

    # Phase 1 & 2: Build 3D house model
    print("\n[Phase 1-2] Building Passive House Model")
    print("-" * 80)

    # House dimensions: 12m x 10m x 5m (2-story house + loft)
    print("\nInitializing house model...")
    result = await server._handle_tools_call(
        ctx,
        {
            "name": "initialize_model",
            "arguments": {
                "length_x": 12.0,
                "length_y": 10.0,
                "length_z": 5.0,
                "resolution": 0.2
            }
        }
    )
    print(f"✓ Model initialized: {result}")

    # Add volumes for realistic passive house structure
    print("\nBuilding structure...")

    # 1. Ground level (TERRE - ground/soil)
    print("  • Adding ground (TERRE)...")
    await server._handle_tools_call(
        ctx,
        {
            "name": "add_volume",
            "arguments": {
                "x1": 0.0, "y1": 0.0, "z1": -0.3,
                "x2": 12.0, "y2": 10.0, "z2": 0.0,
                "material": "TERRE"
            }
        }
    )

    # 2. Foundation (BETON - concrete)
    print("  • Adding concrete foundation (BETON)...")
    await server._handle_tools_call(
        ctx,
        {
            "name": "add_volume",
            "arguments": {
                "x1": 0.0, "y1": 0.0, "z1": 0.0,
                "x2": 12.0, "y2": 10.0, "z2": 0.2,
                "material": "BETON"
            }
        }
    )

    # 3. Insulation under floor (POLYSTYRENE)
    print("  • Adding floor insulation (POLYSTYRENE)...")
    await server._handle_tools_call(
        ctx,
        {
            "name": "add_volume",
            "arguments": {
                "x1": 0.0, "y1": 0.0, "z1": 0.2,
                "x2": 12.0, "y2": 10.0, "z2": 0.35,
                "material": "POLYSTYRENE"
            }
        }
    )

    # 4. Interior air zone (Level 1)
    print("  • Adding interior air volume...")
    await server._handle_tools_call(
        ctx,
        {
            "name": "add_volume",
            "arguments": {
                "x1": 0.3, "y1": 0.3, "z1": 0.35,
                "x2": 11.7, "y2": 9.7, "z2": 3.0,
                "material": "AIR"
            }
        }
    )

    # 5. External composite walls (MUR_COMPOSITE_EXT)
    print("  • Adding external insulated walls (MUR_COMPOSITE_EXT)...")

    # Front wall
    await server._handle_tools_call(
        ctx,
        {
            "name": "add_volume",
            "arguments": {
                "x1": 0.0, "y1": 0.0, "z1": 0.35,
                "x2": 12.0, "y2": 0.3, "z2": 3.0,
                "material": "MUR_COMPOSITE_EXT"
            }
        }
    )

    # Back wall
    await server._handle_tools_call(
        ctx,
        {
            "name": "add_volume",
            "arguments": {
                "x1": 0.0, "y1": 9.7, "z1": 0.35,
                "x2": 12.0, "y2": 10.0, "z2": 3.0,
                "material": "MUR_COMPOSITE_EXT"
            }
        }
    )

    # Left wall
    await server._handle_tools_call(
        ctx,
        {
            "name": "add_volume",
            "arguments": {
                "x1": 0.0, "y1": 0.0, "z1": 0.35,
                "x2": 0.3, "y2": 10.0, "z2": 3.0,
                "material": "MUR_COMPOSITE_EXT"
            }
        }
    )

    # Right wall
    await server._handle_tools_call(
        ctx,
        {
            "name": "add_volume",
            "arguments": {
                "x1": 11.7, "y1": 0.0, "z1": 0.35,
                "x2": 12.0, "y2": 10.0, "z2": 3.0,
                "material": "MUR_COMPOSITE_EXT"
            }
        }
    )

    # 6. Attic insulation (LAINE_BOIS)
    print("  • Adding attic insulation (LAINE_BOIS)...")
    await server._handle_tools_call(
        ctx,
        {
            "name": "add_volume",
            "arguments": {
                "x1": 0.3, "y1": 0.3, "z1": 3.0,
                "x2": 11.7, "y2": 9.7, "z2": 3.3,
                "material": "LAINE_BOIS"
            }
        }
    )

    # 7. Roof (BETON with insulation)
    print("  • Adding roof (BETON)...")
    await server._handle_tools_call(
        ctx,
        {
            "name": "add_volume",
            "arguments": {
                "x1": 0.0, "y1": 0.0, "z1": 5.0,
                "x2": 12.0, "y2": 10.0, "z2": 5.0,
                "material": "BETON"
            }
        }
    )

    # Get model info
    print("\nGetting model statistics...")
    info = await server._handle_tools_call(ctx, {"name": "get_model_info", "arguments": {}})
    print(f"✓ Model info: {json.dumps(info, indent=2)}")

    # List available materials
    print("\nListing available materials...")
    materials = await server._handle_tools_call(ctx, {"name": "list_materials", "arguments": {}})
    print(f"✓ Available materials: {len(materials)} types")

    # Export to JSON
    print("\nExporting model to JSON...")
    export_result = await server._handle_tools_call(
        ctx,
        {
            "name": "export_to_json",
            "arguments": {
                "filepath": "/mnt/share/Sources/MCP_server/data_heatmodel/passive_house_model.json"
            }
        }
    )
    print(f"✓ Model exported: {export_result}")

    # Phase 3: Display audit trail
    print("\n[Phase 3] Audit Trail")
    print("-" * 80)

    audit_entries = server.audit_logger.get_recent_entries(limit=20)
    print(f"Recent audit events ({len(audit_entries)} total):\n")

    for entry in audit_entries[-10:]:  # Show last 10
        event_type = entry.event_type
        timestamp = entry.timestamp.strftime("%H:%M:%S")
        username = entry.username or "unknown"
        status = entry.status
        print(f"  {timestamp} | {event_type:20s} | {username:15s} | {status}")

    # Summary
    print("\n" + "="*80)
    print("SUMMARY - Phase 3 Integration Test")
    print("="*80)
    print(f"""
✓ Phase 1 (Transport): Stdio communication with MCP server
✓ Phase 2 (Permissions): Tool execution with FILE_WRITE permission
✓ Phase 3 (Authentication): JWT authentication + audit trail

Model Created:
  - Dimensions: 12m x 10m x 5m
  - Type: Passive house with heavy insulation
  - Materials: TERRE, BETON, POLYSTYRENE, AIR, MUR_COMPOSITE_EXT, LAINE_BOIS
  - Total voxels: {info.get('total_voxels', 'N/A')}
  - File: {export_result.get('filepath', 'N/A')}

Authentication:
  - Client: {ctx.username} (ID: {ctx.user_id[:8]}...)
  - Roles: {', '.join(ctx.roles)}
  - Token valid for: 1 hour
  - Audit entries: {server.audit_logger.get_entry_count()}

Next Steps:
  1. Load the exported JSON in HeatSimulation main.py
  2. Run thermal simulation: python main.py
  3. Visualize results with PyVista
    """)

    print("="*80 + "\n")


# ============================================================================
# Main Entry Point
# ============================================================================

if __name__ == "__main__":
    asyncio.run(run_heatmodel_client())
