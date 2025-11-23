# Phase 6 - Architecture Technique: Isolation par Processus

## 🎯 Vue d'ensemble

Phase 6 améliore la sécurité du serveur MCP en :
1. **Isolant les répertoires par client** - Chaque client opère dans son dossier
2. **Exécutant le code dans des subprocesses** - Code runs in isolated process
3. **Gérant les ressources par client** - CPU/Memory/Disk quotas
4. **Persistant l'état sandbox** - Variables survient entre appels
5. **Ajoutant des permissions croisées** - Accès contrôlé entre clients

---

## 🏗️ Architecture en couches

```
┌─────────────────────────────────────────────────────┐
│         MCP Protocol Layer (Existing)               │
│         - JSON-RPC 2.0, tools/call, etc             │
└────────────────┬────────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────────┐
│      MCPServer + ToolManager (Phase 2-4)            │
│      - Tool registry, routing                       │
└────────────────┬────────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────────┐
│  ExecutionManager (Phase 2, Updated Phase 6)        │
│  - Tool validation                                  │
│  - Permission checking                             │
│  - Call SubprocessExecutor instead of direct exec  │
└────────────────┬────────────────────────────────────┘
                 │
        ┌────────┴──────────────┐
        │                       │
┌───────▼──────────┐   ┌───────▼──────────────────┐
│ Permission       │   │ ClientIsolationManager   │
│ Manager (Phase3) │   │ (NEW Phase 6)            │
│ - Verify access  │   │ - Map paths to dirs      │
│ - RBAC checks    │   │ - Validate file access   │
│ + New perms:     │   │ - Support cross-client   │
│   FILE_READ_     │   │   access with permission │
│   CROSS_CLIENT   │   │                          │
│   FILE_WRITE_    │   │                          │
│   CROSS_CLIENT   │   │                          │
│   QUOTA_OVERRIDE │   │                          │
└──────────────────┘   └───────────────────────────┘
                              │
┌─────────────────────────────┼─────────────────────┐
│                             │                     │
┌──────────────────┐  ┌───────▼──────────┐  ┌─────▼───────────┐
│ResourceManager   │  │SubprocessExecutor│  │SandboxState     │
│(NEW Phase 6)     │  │(NEW Phase 6)     │  │Manager          │
│                  │  │                  │  │(NEW Phase 6)    │
│- Track quotas    │  │- Create subprocess   │- Load state.json│
│- Enforce limits  │  │- Run code in process │- Save state     │
│- Monitor CPU/RAM │  │- Handle timeout      │- Serialize vars │
│- Per-client      │  │- Get results via     │- Per-client     │
│  allocation      │  │  JSON stdout         │  persistence    │
└──────────────────┘  └──────────────────┘  └─────────────────┘
        │                      │                      │
        └──────────┬───────────┴──────────┬──────────┘
                   │                      │
        ┌──────────▼──────────┐  ┌───────▼──────────┐
        │   Subprocess Child  │  │ File System      │
        │   Python process    │  │ data/clients/... │
        │   - Isolated env    │  │ - Per-client dir │
        │   - Working dir =   │  │ - state.json     │
        │     client isolated │  │ - Persisted vars │
        └─────────────────────┘  └──────────────────┘
```

---

## 📦 Composants Détaillés

### 1. SubprocessExecutor

Exécute le code dans un processus enfant avec gestion de timeout.

**Fichier**: `mcp_server/resources/subprocess_executor.py`

**Classe principale**:
```python
class SubprocessExecutor:
    """
    Exécute du code dans un subprocess Python avec timeout.

    Features:
    - Crée subprocess avec environment isolé
    - Pass code + context via stdin JSON
    - Timeout configurable (défaut 30s)
    - SIGTERM puis SIGKILL après timeout
    - Récupère résultats via stdout JSON
    - Gère les processus morts/crashed
    """

    async def execute(
        self,
        code: str,
        client_id: str,
        working_dir: Path,
        timeout: float = 30.0,
        context: Dict[str, Any] = None,
        max_retries: int = 3
    ) -> Dict[str, Any]:
        """
        Exécute le code dans un subprocess.

        Args:
            code: Python code à exécuter
            client_id: ID du client
            working_dir: Répertoire de travail du subprocess
            timeout: Timeout en secondes (défaut 30s)
            context: Variables globales pré-chargées
            max_retries: Retries si crash

        Returns:
            {"result": ..., "stdout": ..., "stderr": ...}

        Raises:
            TimeoutError: Si timeout atteint
            SubprocessCrashError: Si process crash
            PermissionError: Si code dangereux détecté
        """
```

**Responsabilités**:
- ✅ Créer subprocess Python (`python -u`)
- ✅ Passer code + context via stdin JSON
- ✅ Gérer les timeouts (SIGTERM → SIGKILL)
- ✅ Capturer stdout/stderr
- ✅ Récupérer résultats via stdout JSON
- ✅ Cleanup processus après exécution
- ✅ Audit logging pour chaque exécution

**Pseudo-code d'exécution**:
```
1. Créer subprocess: python -u {wrapper_script}
2. Envoyer via stdin:
   {
     "code": "print('hello')",
     "context": {...},
     "client_id": "alice_123"
   }
3. Attendre réponse JSON sur stdout avec timeout
4. Si timeout: SIGTERM (2s) → SIGKILL
5. Parser résultat JSON et retourner
6. Cleanup: tuer subprocess orphelin si nécessaire
```

---

### 2. ClientIsolationManager

Gère l'isolation des répertoires par client et mapping des chemins.

**Fichier**: `mcp_server/resources/client_isolation.py`

**Classe principale**:
```python
class ClientIsolationManager:
    """
    Gère l'isolation des répertoires par client.

    Features:
    - Crée/manager répertoires client
    - Mappe chemins relatifs → répertoires isolés
    - Valide accès aux fichiers
    - Support accès croisé avec permission
    """

    def __init__(self, data_dir: Path = Path("data/clients")):
        """Initialize isolation manager"""
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def get_client_directory(self, client_id: str) -> Path:
        """
        Récupère le répertoire isolé d'un client.

        Returns:
            Path: data/clients/{client_id}/

        Note: Crée le répertoire s'il n'existe pas
        """

    def resolve_path(
        self,
        client_id: str,
        relative_path: str
    ) -> Path:
        """
        Résout un chemin relatif vers le répertoire client.

        Examples:
            alice, "data.txt" → data/clients/alice_123/data.txt
            alice, "files/doc.pdf" → data/clients/alice_123/files/doc.pdf
            alice, "/etc/passwd" → REJECT (absolute path)
            alice, "../../../etc/passwd" → REJECT (escape attempt)

        Args:
            client_id: ID du client
            relative_path: Chemin relatif demandé

        Returns:
            Path: Chemin absolu sécurisé

        Raises:
            ValueError: Si chemin invalide (absolute, escape attempt)
        """

    def validate_access(
        self,
        client_id: str,
        target_path: Path,
        permission: Permission,
        permission_manager: 'PermissionManager'
    ) -> bool:
        """
        Vérifie si un client peut accéder à un fichier.

        Rules:
        - Si target in client_dir: OK si permission FILE_READ/FILE_WRITE
        - Si target NOT in client_dir:
          - Refuser sauf si permission FILE_READ_CROSS_CLIENT/FILE_WRITE_CROSS_CLIENT
          - Encore vérifier que permission est accordée

        Args:
            client_id: ID du client
            target_path: Chemin absolu du fichier
            permission: Permission demandée
            permission_manager: PermissionManager pour vérifier

        Returns:
            bool: True si accès autorisé
        """

    def list_client_files(self, client_id: str) -> List[Path]:
        """List all files in client's directory"""

    def clear_client_directory(self, client_id: str) -> None:
        """Clear all files in client's directory (logout cleanup)"""
```

**Responsabilités**:
- ✅ Créer répertoire `data/clients/{client_id}/` pour chaque client
- ✅ Mapper chemins relatifs → répertoires isolés
- ✅ Refuser chemins absolus et escape attempts (`../../../`)
- ✅ Vérifier permissions pour accès croisé (FILE_READ_CROSS_CLIENT, etc.)
- ✅ Audit logging des accès aux fichiers

**Pseudo-code validation**:
```
validate_access(alice, data/clients/bob_123/secret.txt, FILE_READ):
1. alice_dir = data/clients/alice_123/
2. target = data/clients/bob_123/secret.txt
3. Check if target is inside alice_dir:
   - NO: Not in her directory
   - Check permission FILE_READ_CROSS_CLIENT on alice
   - If not: REJECT
   - If yes: ALLOW
4. Check if target is inside alice_dir:
   - YES: Check permission FILE_READ
   - If not: REJECT
   - If yes: ALLOW
```

---

### 3. ResourceManager

Gère les quotas de ressources (CPU, mémoire, disque) par client.

**Fichier**: `mcp_server/resources/resource_manager.py`

**Classes principales**:
```python
@dataclass
class ClientQuotas:
    """Resource quotas for a client"""
    cpu_percent: float = 50.0      # Max CPU usage (%)
    memory_mb: int = 512           # Max memory (MB)
    disk_gb: int = 1               # Max disk space (GB)
    concurrent_processes: int = 5  # Max subprocess concurrently


class ResourceManager:
    """
    Gère les quotas de ressources par client.

    Features:
    - Définit quotas par client
    - Vérifie disponibilité avant exécution
    - Alloue ressources pendant subprocess
    - Libère ressources après subprocess
    - Audit trail des dépassements
    """

    def __init__(self):
        self.client_quotas: Dict[str, ClientQuotas] = {}
        self.client_usage: Dict[str, ResourceUsage] = {}
        self.quota_overrides: Set[str] = set()  # Clients with QUOTA_OVERRIDE

    def get_client_quotas(self, client_id: str) -> ClientQuotas:
        """Get quotas for client (defaults if not set)"""

    def set_client_quotas(
        self,
        client_id: str,
        quotas: ClientQuotas
    ) -> None:
        """Set custom quotas for client"""

    def check_availability(
        self,
        client_id: str,
        required: ResourceRequirement,
        has_quota_override: bool = False
    ) -> bool:
        """
        Check if enough resources available for subprocess.

        Args:
            client_id: Client requesting resources
            required: CPU%, Memory MB
            has_quota_override: Whether client has QUOTA_OVERRIDE permission

        Returns:
            bool: True if enough resources

        Note: If QUOTA_OVERRIDE, always return True (ignore quotas)
        """

    def allocate(
        self,
        client_id: str,
        pid: int,
        required: ResourceRequirement
    ) -> None:
        """Allocate resources to subprocess"""

    def release(self, client_id: str, pid: int) -> None:
        """Release resources from subprocess"""

    def get_client_usage(self, client_id: str) -> ResourceUsage:
        """Get current resource usage for client"""

    def record_quota_exceed(
        self,
        client_id: str,
        required: ResourceRequirement,
        available: ResourceRequirement
    ) -> None:
        """Record quota exceed event in audit trail"""
```

**Responsabilités**:
- ✅ Définir quotas par défaut: CPU 50%, RAM 512MB, Disque 1GB
- ✅ Vérifier ressources disponibles avant exécution
- ✅ Si insuffisant ET pas QUOTA_OVERRIDE → PermissionDeniedError
- ✅ Si QUOTA_OVERRIDE → ignorer les quotas
- ✅ Tracker ressources consommées par subprocess
- ✅ Audit trail des dépassements

**Pseudo-code checking**:
```
check_availability(alice, required={cpu: 60%, ram: 600MB}, quota_override=False):
1. quotas = get_client_quotas(alice)  # {cpu: 50%, ram: 512MB, ...}
2. If quota_override:
   - Return True (ignore quotas)
3. Check CPU:
   - if required.cpu (60%) > quotas.cpu_percent (50%):
     - Record audit: "Quota exceed: CPU"
     - Return False
4. Check Memory:
   - current_usage = get_client_usage(alice).memory_mb
   - if (current_usage + required.memory) > quotas.memory_mb:
     - Record audit: "Quota exceed: Memory"
     - Return False
5. Return True (resources available)
```

---

### 4. SandboxStateManager

Gère la persistance de l'état des variables sandbox par client.

**Fichier**: `mcp_server/resources/sandbox_state.py`

**Classe principale**:
```python
class SandboxStateManager:
    """
    Gère la persistance de l'état sandbox par client.

    Features:
    - Sauvegarde variables après exécution
    - Charge variables avant exécution
    - Sérialise via JSON
    - Isolation stricte par client
    """

    async def save_state(
        self,
        client_id: str,
        state: Dict[str, Any]
    ) -> None:
        """
        Sauvegarde l'état sandbox d'un client.

        Saves to: data/clients/{client_id}/state.json

        Args:
            client_id: ID du client
            state: Variables globales à sauvegarder

        Note: Only JSON-serializable objects are saved
        """

    async def load_state(self, client_id: str) -> Dict[str, Any]:
        """
        Charge l'état sandbox d'un client.

        Returns:
            Dict: Loaded state, or {} if file doesn't exist

        Note: If state.json missing (first time), return {}
        """

    async def clear_state(self, client_id: str) -> None:
        """
        Efface l'état sandbox d'un client.

        Deletes: data/clients/{client_id}/state.json

        Note: Called on client logout or reset
        """

    @staticmethod
    def _serialize_state(state: Dict) -> str:
        """Serialize state dict to JSON string"""

    @staticmethod
    def _deserialize_state(json_str: str) -> Dict:
        """Deserialize JSON string to state dict"""
```

**Responsabilités**:
- ✅ Sauvegarder variables globales dans `data/clients/{client_id}/state.json`
- ✅ Charger variables au prochain appel tool du même client
- ✅ Sérialiser seulement les objets JSON (str, int, list, dict, etc.)
- ✅ Isolation stricte: Alice ne voit pas état de Bob
- ✅ Cleanup lors du logout

**Flow d'exécution**:
```
Tool Call #1:
1. SubprocessExecutor.execute(code="x = 42")
2. Subprocess runs code
3. Subprocess returns: {"result": None, "globals": {"x": 42}}
4. SandboxStateManager.save_state(alice, {"x": 42})
5. Saved: data/clients/alice_123/state.json = {"x": 42}

Tool Call #2 (même client alice):
1. SandboxStateManager.load_state(alice)
2. Returns: {"x": 42}
3. SubprocessExecutor.execute(code="print(x)", context={"x": 42})
4. Subprocess gets x=42 in globals
5. Prints "42"
```

---

## 🔐 New Permissions (Phase 6)

Ajout de 3 nouvelles permissions au système RBAC existant:

```python
class PermissionType(Enum):
    # Existing (Phase 2-3)
    FILE_READ = "file_read"
    FILE_WRITE = "file_write"
    FILE_WRITE_GLOBAL = "file_write_global"
    CODE_EXECUTION = "code_execution"
    CODE_EXECUTION_SUDO = "code_execution_sudo"
    SYSTEM_COMMAND = "system_command"

    # New (Phase 6)
    FILE_READ_CROSS_CLIENT = "file_read_cross_client"      # Read other clients' files
    FILE_WRITE_CROSS_CLIENT = "file_write_cross_client"    # Write other clients' files
    QUOTA_OVERRIDE = "quota_override"                      # Ignore resource quotas
```

**Utilisation**:
```python
# Grant permission to read other clients' files
server.grant_permission(
    client_id="alice",
    permission=Permission(
        PermissionType.FILE_READ_CROSS_CLIENT,
        path="data/clients/*"
    )
)

# Grant permission to ignore quotas
server.grant_permission(
    client_id="admin",
    permission=Permission(PermissionType.QUOTA_OVERRIDE)
)
```

---

## 📂 Structure des répertoires (Phase 6)

```
data/
└── clients/                              # NEW: Client isolation directories
    ├── alice_client_uuid_123/
    │   ├── state.json                    # Persisted sandbox variables
    │   ├── files/                        # Client-created files
    │   │   ├── report.pdf
    │   │   └── data.csv
    │   └── ...
    ├── bob_client_uuid_456/
    │   ├── state.json
    │   ├── files/
    │   └── ...
    └── system_admin_789/
        ├── state.json
        └── ...
```

---

## 🔄 Flow d'exécution d'un Tool Call (Phase 6)

```
Client Alice calls: tools/call("execute_code", code="print('hello')")

1. Protocol Layer: Parse JSON-RPC request
   ↓
2. MCPServer: Route to execute_code tool
   ↓
3. ExecutionManager.execute_tool():
   a. Load tool definition
   b. Validate parameters against schema
   c. Check client authentication (Phase 3)
   d. Check permissions (Phase 2)
      - FILE_READ, FILE_WRITE, CODE_EXECUTION
      - FILE_READ_CROSS_CLIENT, FILE_WRITE_CROSS_CLIENT (new)
      - QUOTA_OVERRIDE (new)
   ↓
4. PermissionManager.check_permission():
   - Verify CODE_EXECUTION granted
   - Verify QUOTA_OVERRIDE if needed
   ↓
5. ClientIsolationManager.validate_access():
   - Map working_dir to data/clients/alice_123/
   - Verify no file access outside isolated dir
   - Verify FILE_READ_CROSS_CLIENT if accessing other client's files
   ↓
6. ResourceManager.check_availability():
   - Check if CPU/Memory available
   - If QUOTA_OVERRIDE permission: ignore quotas
   - If insufficient: raise PermissionDeniedError
   ↓
7. SandboxStateManager.load_state():
   - Load previous sandbox state from data/clients/alice_123/state.json
   - If file doesn't exist: start with empty dict
   ↓
8. SubprocessExecutor.execute():
   a. Create subprocess: python -u wrapper.py
   b. Send via stdin JSON:
      {
        "code": "print('hello')",
        "context": {/* loaded state */},
        "client_id": "alice_123"
      }
   c. Wait for results with timeout (30s default)
   d. If timeout: SIGTERM (2s) → SIGKILL
   e. Parse JSON response from stdout
   f. Return: {"result": "hello", "stdout": "hello\n", ...}
   ↓
9. SandboxStateManager.save_state():
   - Extract globals from subprocess result
   - Save to data/clients/alice_123/state.json
   ↓
10. ExecutionManager return result to Protocol Layer
   ↓
11. Protocol Layer: Return JSON-RPC response to client
```

---

## 🧪 Integration Test Plan (Phase 6)

15-20 integration tests covering:

1. **Isolation Tests** (4 tests)
   - Client A can read own files
   - Client A cannot read Client B files without permission
   - Client A with FILE_READ_CROSS_CLIENT can read Client B files
   - Path traversal attacks blocked

2. **Subprocess Tests** (4 tests)
   - Normal code execution
   - Code with timeout (code sleeps 100s)
   - Code that crashes (divide by zero)
   - Multiple concurrent subprocesses

3. **Quota Tests** (4 tests)
   - Code within quota: executes
   - Code exceeds quota: rejected
   - QUOTA_OVERRIDE permission: executes
   - Multiple clients with different quotas

4. **State Persistence Tests** (3 tests)
   - Variables persist between calls
   - Different clients have different state
   - State cleared on logout

5. **Permission Tests** (2 tests)
   - FILE_READ_CROSS_CLIENT enforced
   - QUOTA_OVERRIDE permission enforced

---

## ✅ Definition of Done (Phase 6)

- [ ] All 4 components implemented (SubprocessExecutor, ClientIsolationManager, ResourceManager, SandboxStateManager)
- [ ] 25-30 unit tests passing
- [ ] 15-20 integration tests passing
- [ ] All Phase 1-5 tests still passing (backward compat)
- [ ] Documentation updated (README, CHANGELOG, examples)
- [ ] Code reviewed and committed
- [ ] Example usage client created
- [ ] Security audit passed

---

**Ready to start Phase 6 implementation?** 🚀
