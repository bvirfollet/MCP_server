# Architecture Phase 2 : Tools & Permissions Management

**Date** : 2025-11-23
**Phase** : 2
**Status** : En Design

---

## 1. Décisions Architecturales

### 1.1 Enregistrement des Tools - Décorateur

**Décision** : Utiliser le décorateur `@server.tool()`

```python
# Approche choisie
@server.tool(
    name="read_file",
    description="Lire un fichier",
    input_schema={
        "type": "object",
        "properties": {
            "path": {"type": "string"}
        }
    },
    permissions=[Permission(PermissionType.FILE_READ, "*.txt")]
)
def read_file(client_context: ClientContext, path: str) -> dict:
    """Implémentation du tool"""
    pass
```

**Avantages** :
- ✅ Simple et pythonic
- ✅ Déclaratif
- ✅ Intégré au serveur
- ✅ Facile à tester

### 1.2 Isolation d'Exécution - Hybride

**Décision** : Approche hybride (Python Phase 2 → Processus Phase 6)

**Phase 2** :
```
┌─────────────────────────────────┐
│  Namespace Python Sécurisé      │
├─────────────────────────────────┤
│ Restrictions d'imports          │
│ __builtins__ limité             │
│ Whitelist de modules            │
│ AST parsing pour détection      │
│ Timeout d'exécution             │
└─────────────────────────────────┘
```

**Phase 6** :
```
┌─────────────────────────────────┐
│  Processus Séparé               │
├─────────────────────────────────┤
│ Fork subprocess par exécution    │
│ User/Group isolation (Linux)    │
│ cgroups pour limiter ressources │
│ Timeout système                 │
│ Communication par stdin/stdout  │
└─────────────────────────────────┘
```

**Phase 2 Détails** :
- Pas d'imports système (os, subprocess, etc.)
- Pas d'accès à __builtins__ complet
- Modules autorisés : json, math, re, datetime
- Timeout par défaut : 30 secondes
- Limite mémoire : 512MB

### 1.3 Permissions - Minimales + Explicites

**Décision** : Permissions par défaut minimales + demande explicite

**Par Défaut (Phase 1)** :
```python
DEFAULT_CLIENT_PERMISSIONS = [
    Permission(PermissionType.FILE_READ, "/app/data/public/*"),
    Permission(PermissionType.SYSTEM_COMMAND, ["echo"]),  # Commandes sûres
]
```

**À la Demande** :
- Client demande au démarrage
- Administrateur approuve
- Permissions enregistrées par client
- Audit logging de chaque appel

---

## 2. Nouvelles Classes et Interfaces

### 2.1 Classe Tool (Abstraite)

```python
class Tool(ABC):
    """Classe abstraite pour tous les tools"""

    # Attributs de classe
    name: str                          # Identifiant unique
    description: str                   # Description pour l'IA
    input_schema: Dict[str, Any]      # JSON Schema pour params
    output_schema: Dict[str, Any]     # JSON Schema pour résultat
    permissions: List[Permission]     # Permissions requises

    # Méthodes
    @abstractmethod
    async def execute(
        self,
        client: ClientContext,
        params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Exécuter le tool"""
        pass

    def get_info(self) -> Dict[str, Any]:
        """Retourner les infos pour exposition MCP"""
        pass
```

### 2.2 Dataclass Permission

```python
@dataclass
class Permission:
    """Représentation d'une permission"""

    type: PermissionType              # Exemple: FILE_READ
    resource: Optional[str] = None    # Chemin, pattern, etc.
    restricted: bool = True           # Si execution restreinte
    parameters: Dict[str, Any] = field(default_factory=dict)

    def matches(self, other: Permission) -> bool:
        """Vérifier si cette permission couvre autre"""
        pass

    def to_dict(self) -> Dict[str, Any]:
        """Sérialiser pour audit"""
        pass
```

### 2.3 Classe ToolManager

```python
class ToolManager:
    """Gestion du registre des tools"""

    def __init__(self):
        self._tools: Dict[str, Tool] = {}
        self._logger = logging.getLogger("tools.manager")

    def register(self, tool: Tool) -> None:
        """Enregistrer un tool"""
        pass

    def unregister(self, tool_name: str) -> None:
        """Désenregistrer un tool"""
        pass

    def get(self, tool_name: str) -> Optional[Tool]:
        """Récupérer un tool par nom"""
        pass

    def list_all(self) -> Dict[str, Tool]:
        """Lister tous les tools"""
        pass

    def get_info_for_client(self, client: ClientContext) -> List[Dict]:
        """Lister tools + permissions pour client"""
        pass
```

### 2.4 Classe PermissionManager

```python
class PermissionManager:
    """Gestion et vérification des permissions"""

    def __init__(self):
        self._client_permissions: Dict[str, List[Permission]] = {}
        self._logger = logging.getLogger("security.permissions")

    def grant_permission(
        self,
        client_id: str,
        permission: Permission
    ) -> None:
        """Accorder une permission à un client"""
        pass

    def revoke_permission(
        self,
        client_id: str,
        permission_type: PermissionType
    ) -> None:
        """Révoquer une permission"""
        pass

    def has_permission(
        self,
        client: ClientContext,
        required: Permission
    ) -> bool:
        """Vérifier si client a la permission"""
        pass

    def check_permission(
        self,
        client: ClientContext,
        required: Permission
    ) -> None:
        """Vérifier et lever exception si refusé"""
        pass

    def get_client_permissions(self, client_id: str) -> List[Permission]:
        """Lister les permissions d'un client"""
        pass
```

### 2.5 Classe ExecutionManager

```python
class ExecutionManager:
    """Exécution sécurisée des tools"""

    def __init__(
        self,
        default_timeout: int = 30,
        max_memory_mb: int = 512
    ):
        self._timeout = default_timeout
        self._max_memory = max_memory_mb
        self._logger = logging.getLogger("execution.manager")

    async def execute_tool(
        self,
        tool: Tool,
        client: ClientContext,
        params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Exécuter un tool de manière sécurisée"""
        # 1. Valider les paramètres
        # 2. Vérifier les permissions
        # 3. Exécuter dans namespace sécurisé
        # 4. Capturer résultat ou erreur
        # 5. Log l'exécution
        # 6. Retourner résultat
        pass

    async def _validate_params(
        self,
        params: Dict[str, Any],
        schema: Dict[str, Any]
    ) -> None:
        """Valider les paramètres contre le schéma"""
        pass

    async def _execute_in_safe_namespace(
        self,
        func: Callable,
        client: ClientContext,
        params: Dict[str, Any],
        timeout: int
    ) -> Dict[str, Any]:
        """Exécuter dans un namespace sécurisé"""
        pass
```

### 2.6 Classe SandboxContext

```python
class SandboxContext:
    """Contexte d'exécution isolé pour chaque client"""

    def __init__(self, client_id: str, working_dir: str):
        self.client_id = client_id
        self.working_dir = working_dir
        self._execution_env: Dict[str, Any] = {}
        self._variables: Dict[str, Any] = {}

    def set_variable(self, name: str, value: Any) -> None:
        """Stocker une variable locale"""
        pass

    def get_variable(self, name: str) -> Any:
        """Récupérer une variable"""
        pass

    def clear(self) -> None:
        """Nettoyer le contexte"""
        pass
```

---

## 3. Architecture Complète - Phase 2

```
┌─────────────────────────────────────────────────────────┐
│           MCPServer (Orchestrateur Principal)           │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌─────────────────┐      ┌──────────────────┐        │
│  │  ToolManager    │──────│  ToolRegistry    │        │
│  ├─────────────────┤      ├──────────────────┤        │
│  │ - register()    │      │ - tools: Dict    │        │
│  │ - get()         │      │                  │        │
│  │ - list_all()    │      └──────────────────┘        │
│  └────────┬────────┘                                   │
│           │                                            │
│  ┌────────▼──────────────┐   ┌──────────────────┐    │
│  │ PermissionManager      │───│ Permission DB    │    │
│  ├───────────────────────┤   ├──────────────────┤    │
│  │ - has_permission()    │   │ client_perms[]   │    │
│  │ - check_permission()  │   │                  │    │
│  │ - grant_permission()  │   └──────────────────┘    │
│  └────────┬──────────────┘                            │
│           │                                            │
│  ┌────────▼──────────────┐   ┌──────────────────┐    │
│  │ ExecutionManager       │───│ SandboxContext[] │    │
│  ├───────────────────────┤   ├──────────────────┤    │
│  │ - execute_tool()      │   │ Per-client state │    │
│  │ - validate_params()   │   │                  │    │
│  │ - safe_namespace()    │   └──────────────────┘    │
│  └────────┬──────────────┘                            │
│           │                                            │
│           ▼                                            │
│  ┌──────────────────────────────────────────┐        │
│  │  Tools (Enregistrés avec @server.tool)   │        │
│  ├──────────────────────────────────────────┤        │
│  │ - tool_1: read_file                      │        │
│  │ - tool_2: write_file                     │        │
│  │ - tool_3: list_files                     │        │
│  │ - tool_N: ...                            │        │
│  └──────────────────────────────────────────┘        │
│                                                       │
└─────────────────────────────────────────────────────┘
```

---

## 4. Flux de Données - Appel Tool

```
1. Client envoie "tools/call" request
   │
   ├─→ {
   │     "jsonrpc": "2.0",
   │     "method": "tools/call",
   │     "params": {
   │       "name": "read_file",
   │       "arguments": {"path": "/app/data/file.txt"}
   │     },
   │     "id": "123"
   │   }
   │
2. MCPProtocolHandler reçoit
   │
   ├─→ Route vers handler tools/call
   │
3. Handler appelle ExecutionManager.execute_tool()
   │
   ├─→ Valide les paramètres (JSON schema)
   ├─→ Récupère le Tool du ToolManager
   ├─→ Vérifie permissions avec PermissionManager
   │
   │   Si refusé:
   │   └─→ Retour erreur permission_denied
   │
   │   Si accepté:
   │   └─→ Exécute dans safe namespace
   │       ├─→ Timeout protection
   │       ├─→ Memory limits
   │       ├─→ Import restrictions
   │       └─→ Capture output/errors
   │
4. ExecutionManager log l'appel (audit)
   │
   ├─→ {
   │     "timestamp": "...",
   │     "event_type": "tool_called",
   │     "client_id": "...",
   │     "tool_name": "read_file",
   │     "status": "success/failed",
   │     "execution_time_ms": 45
   │   }
   │
5. Retour du résultat au client
   │
   ├─→ {
   │     "jsonrpc": "2.0",
   │     "result": {
   │       "content": "...",
   │       "size": 1024
   │     },
   │     "id": "123"
   │   }
```

---

## 5. Intégration avec Phase 1

### Modifications MCPServer

```python
class MCPServer:

    def __init__(self, ...):
        super().__init__()

        # Phase 2 additions
        self.tool_manager = ToolManager()
        self.permission_manager = PermissionManager()
        self.execution_manager = ExecutionManager()

        # Register Phase 2 method handlers
        self.register_method("tools/list", self._handle_tools_list)
        self.register_method("tools/call", self._handle_tools_call)

    def tool(self, name: str, description: str, ...):
        """Décorateur pour enregistrer des tools"""
        def decorator(func):
            tool = FunctionTool(name, description, func, ...)
            self.tool_manager.register(tool)
            return func
        return decorator

    async def _handle_tools_list(
        self,
        client: ClientContext,
        params: dict
    ) -> dict:
        """Handler pour tools/list"""
        tools_info = self.tool_manager.get_info_for_client(client)
        return {"tools": tools_info}

    async def _handle_tools_call(
        self,
        client: ClientContext,
        params: dict
    ) -> dict:
        """Handler pour tools/call"""
        tool_name = params.get("name")
        arguments = params.get("arguments", {})

        tool = self.tool_manager.get(tool_name)
        if not tool:
            raise ToolNotFoundError(tool_name)

        result = await self.execution_manager.execute_tool(
            tool, client, arguments
        )
        return result
```

---

## 6. Matrice de Sécurité Phase 2

| Menace | Phase 2 | Mitigation |
|--------|---------|-----------|
| Code injection | ✅ | Namespace sécurisé, AST parsing |
| Path traversal | ✅ | Validation canonique chemins |
| Permission escalation | ✅ | Vérification stricte avant exécution |
| DoS (CPU) | ✅ | Timeout exécution (30s) |
| DoS (Memory) | ✅ | Limite mémoire (512MB) |
| DoS (Files) | ✅ | Limite fichiers ouverts |
| Information disclosure | ✅ | Isolation contexte client |
| Unauthorized access | ✅ | Permission check |

---

## 7. Détails d'Implémentation - Safe Namespace

### Modules Autorisés Phase 2
```python
SAFE_MODULES = {
    "json": json,
    "math": math,
    "re": re,
    "datetime": datetime,
    "collections": collections,
    "functools": functools,
    "itertools": itertools,
}
```

### Builtins Restreints
```python
SAFE_BUILTINS = {
    "len", "str", "int", "float", "bool", "list", "dict", "set", "tuple",
    "range", "enumerate", "zip", "map", "filter", "sorted", "reversed",
    "sum", "min", "max", "abs", "round", "pow", "isinstance", "type",
    "print",  # Capturé pour output
    "open",   # Avec restrictions de chemin
}
```

### Détection AST - Patterns Bloqués
```python
BLOCKED_AST_PATTERNS = {
    "ast.Import": ["os", "sys", "subprocess", "shutil"],
    "ast.ImportFrom": ["os", "sys", "subprocess"],
    "ast.Attribute": ["__dict__", "__class__", "__import__"],
    "ast.Call": ["exec", "eval", "compile", "__import__"],
}
```

---

## 8. Structure des Fichiers Phase 2

```
mcp_server/
├── tools/
│   ├── __init__.py
│   ├── tool.py                 # Classe Tool abstraite
│   ├── tool_manager.py         # ToolManager
│   └── builtin_tools.py        # Tools de base (optionnel)
│
├── resources/
│   ├── __init__.py
│   ├── execution_manager.py    # ExecutionManager
│   ├── sandbox_context.py      # SandboxContext
│   └── safe_namespace.py       # Namespace sécurisé
│
├── security/
│   ├── permission.py           # Permission dataclass
│   └── permission_manager.py   # PermissionManager
│
└── core/
    └── mcp_server.py           # Modifications pour Phase 2

tests/
├── test_tool_manager.py        # Tests ToolManager
├── test_permission_manager.py  # Tests PermissionManager
├── test_execution_manager.py   # Tests ExecutionManager
└── test_integration_phase2.py  # Tests d'intégration
```

---

## 9. Critères de Succès Phase 2

### Code
- ✅ 6 nouveaux modules créés
- ✅ 50+ tests unitaires écrits
- ✅ 20+ tests d'intégration
- ✅ 100% test pass rate
- ✅ Couverture de code > 95%

### Fonctionnalité
- ✅ Tools enregistrables avec décorateur
- ✅ tools/list expose tools correctement
- ✅ tools/call exécute de manière sécurisée
- ✅ Permissions vérifiées avant exécution
- ✅ Timeout et limites respectées
- ✅ Audit logging complet

### Sécurité
- ✅ Aucune injection de code possible
- ✅ Aucune escalade de privilèges
- ✅ Isolation contexte client garantie
- ✅ Tous les patterns dangereux bloqués
- ✅ Chemins validés correctement

### Performance
- ✅ Exécution < 100ms (hors I/O)
- ✅ Pas de memory leaks
- ✅ Pas de file descriptor leaks

---

## 10. Dépendances et Imports Externes

**Aucune dépendance externe requise pour Phase 2** ✅
- Tout implémenté en Python pur
- Utilise stdlib: json, re, datetime, collections, functools, itertools, ast, textwrap

---

**Architecture Phase 2 complète et prête pour implémentation !**

Voir USECASE2_DEFINITION.md pour les tests d'acceptation détaillés.

