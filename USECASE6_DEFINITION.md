# Phase 6 - Isolation par Processus (Subprocess)

## 📋 Use Cases et Exigences

### UC6.1 - Isolation de répertoire par client

**Objective**: Chaque client MCP dispose d'un répertoire de travail isolé, sans accès aux fichiers d'autres clients par défaut.

**Actors**:
- Client MCP (Alice, Bob)
- Serveur MCP (MCPServer)
- Système de fichiers (OS)

**Main Flow**:
1. Alice se connecte et reçoit authentification JWT
2. Alice appelle tool `read_file("data.txt")`
3. Serveur mappe le chemin `data.txt` → `data/clients/alice_client_id/data.txt`
4. Serveur exécute le subprocess dans le répertoire `data/clients/alice_client_id/`
5. Subprocess ne peut pas accéder à `data/clients/bob_client_id/`

**Acceptance Criteria**:
- ✅ Chaque client a un dossier unique `data/clients/{client_id}/`
- ✅ Les chemins relatifs des clients sont maappés à leur dossier
- ✅ Les chemins absolus sont refusés sauf si permission globale
- ✅ Lors du logout, le dossier du client persiste (pour futur rechargement)
- ✅ Permissions FILE_READ/FILE_WRITE respectent l'isolation

---

### UC6.2 - Subprocess avec timeout

**Objective**: Les outils s'exécutent dans des processus enfants avec timeout et gestion d'erreurs.

**Actors**:
- Tool (CODE_EXECUTION)
- ExecutionManager
- Subprocess Python

**Main Flow**:
1. Client appelle tool `execute_code(code="import time; time.sleep(100)")`
2. ExecutionManager crée un subprocess Python
3. Subprocess exécute le code avec timeout (30s par défaut)
4. Après 30s, subprocess est tué (SIGTERM → SIGKILL)
5. ExecutionManager retourne erreur timeout au client

**Alternate Flow - Normal**:
1. Client appelle tool `execute_code(code="print('hello')")`
2. ExecutionManager crée subprocess
3. Subprocess exécute, code se termine en 100ms
4. Subprocess retourne `{"result": "hello"}`
5. ExecutionManager retourne résultat au client

**Acceptance Criteria**:
- ✅ Chaque tool_call crée un nouveau subprocess
- ✅ Subprocess exécute dans son dossier client isolé
- ✅ Timeout configurable par tool (défaut: 30s)
- ✅ Si timeout: SIGTERM (2s attente) puis SIGKILL
- ✅ Subprocess morts/crashed sont nettoyés
- ✅ Subprocess peut persister d'une call à l'autre pour même client (état persistant)
- ✅ Communication parent-subprocess via JSON stdin/stdout

---

### UC6.3 - Quotas de ressources par client

**Objective**: Chaque client a des quotas CPU/mémoire/disque, les dépassements sont refusés sauf permission spéciale.

**Actors**:
- Client (standard user)
- Client (admin user with QUOTA_OVERRIDE permission)
- ExecutionManager
- ResourceManager

**Main Flow - Denied**:
1. Client "alice" a quota: CPU 50%, Mémoire 512MB, Disque 1GB
2. Alice appelle tool qui consomme 600MB
3. ResourceManager refuse l'exécution → PermissionDeniedError
4. Alice doit attendre libération de ressources ou demander admin

**Main Flow - Allowed (with permission)**:
1. Client "admin" a permission QUOTA_OVERRIDE
2. Admin appelle tool qui consomme 600MB (dépasse le quota)
3. ResourceManager vérifie permission QUOTA_OVERRIDE
4. Exécution autorisée (ignore le quota)

**Acceptance Criteria**:
- ✅ Chaque client a quotas: CPU%, RAM (MB), Disque (GB)
- ✅ Quotas par défaut: CPU 50%, RAM 512MB, Disque 1GB
- ✅ Avant exécution, vérifier ressources disponibles
- ✅ Si insuffisant et pas permission QUOTA_OVERRIDE → refuser
- ✅ Si permission QUOTA_OVERRIDE → ignorer les quotas
- ✅ Tracking ressources consommées par subprocess
- ✅ Audit trail des dépassements de quota

---

### UC6.4 - Persistance des variables sandbox

**Objective**: Les variables sandbox d'un client persistent entre les appels au même serveur, mais pas entre serveurs.

**Actors**:
- Client (alice_session_1)
- ExecutionManager
- SandboxContext

**Main Flow**:
1. Alice appelle `execute_code(code="x = 42; globals()['x'] = 42")`
2. ExecutionManager crée subprocess, exécute, variable `x` persiste dans subprocess state
3. Alice appelle `execute_code(code="print(globals().get('x'))")`
4. Même subprocess (ou rechargement d'état): retourne `42`
5. Alice se déconnecte
6. Alice se reconecte avec nouveau JWT
7. Nouveau subprocess créé: `print(globals().get('x'))` retourne `None`

**Acceptance Criteria**:
- ✅ Variables globales persistent pour un client entre calls
- ✅ Données sauvegardées dans `data/clients/{client_id}/state.json`
- ✅ Après reconnexion, état rechargé si même client
- ✅ État isolé par client (Alice ne voit pas état de Bob)

---

### UC6.5 - Permission FILE_READ_CROSS_CLIENT

**Objective**: Certains clients peuvent lire les fichiers d'autres clients avec permission spéciale.

**Actors**:
- Client "alice" (standard)
- Client "bob" (admin with FILE_READ_CROSS_CLIENT)
- ExecutionManager

**Main Flow**:
1. Bob appelle `read_file("../../../clients/alice_client_id/secret.txt")`
2. ExecutionManager normalise le chemin
3. Bob n'a pas permission FILE_READ_CROSS_CLIENT → refuser
4. Alice appelle même chose
5. Alice n'a pas permission → refuser

**Alternate - Allowed**:
1. Bob reçoit permission FILE_READ_CROSS_CLIENT via grant_permission
2. Bob appelle `read_file("../../../clients/alice_client_id/secret.txt")`
3. Chemin normalisé et permission vérifiée
4. Bob peut lire le fichier d'Alice

**Acceptance Criteria**:
- ✅ Nouveau type permission: FILE_READ_CROSS_CLIENT
- ✅ Nouveau type permission: FILE_WRITE_CROSS_CLIENT
- ✅ Par défaut, clients isolés (pas d'accès croisé)
- ✅ Avec permission, accès croisé autorisé
- ✅ Audit trail des accès croisés

---

### UC6.6 - Permission QUOTA_OVERRIDE

**Objective**: Certains clients peuvent ignorer les quotas de ressources.

**Actors**:
- Client "user" (standard quota)
- Client "admin" (QUOTA_OVERRIDE permission)

**Main Flow - User denied**:
1. User a quota: CPU 50%, RAM 512MB
2. User appelle code qui consomme 600MB
3. ResourceManager refuse → PermissionDeniedError

**Main Flow - Admin allowed**:
1. Admin a permission QUOTA_OVERRIDE
2. Admin appelle code qui consomme 600MB
3. ResourceManager vérifie permission QUOTA_OVERRIDE
4. Exécution autorisée

**Acceptance Criteria**:
- ✅ Nouveau type permission: QUOTA_OVERRIDE
- ✅ Par défaut, clients respectent les quotas
- ✅ Avec permission, quotas ignorés
- ✅ Audit trail des utilisations QUOTA_OVERRIDE

---

## 📐 Architecture - Composants

### Component 1: SubprocessExecutor

Gère l'exécution du code dans les subprocesses avec timeout.

**Responsabilités**:
- Créer subprocess Python
- Passer le code et contexte au subprocess
- Gérer timeouts (SIGTERM → SIGKILL)
- Récupérer résultats via JSON stdout
- Cleanup de processus morts

**Interface**:
```python
class SubprocessExecutor:
    async def execute(
        self,
        code: str,
        client_id: str,
        timeout: float = 30.0,
        context: Dict = None
    ) -> Dict[str, Any]:
        """Execute code in subprocess with timeout"""
```

---

### Component 2: ClientIsolationManager

Gère l'isolation des répertoires par client.

**Responsabilités**:
- Créer/manager répertoire par client
- Mapper chemins relatifs → répertoires clients
- Valider accès aux fichiers
- Gérer permissions d'accès croisé

**Interface**:
```python
class ClientIsolationManager:
    def get_client_directory(self, client_id: str) -> Path:
        """Get isolated directory for client"""

    def resolve_path(self, client_id: str, relative_path: str) -> Path:
        """Resolve relative path to absolute within client dir"""

    def validate_access(
        self,
        client_id: str,
        target_path: Path,
        permission: Permission
    ) -> bool:
        """Check if client can access target path"""
```

---

### Component 3: ResourceManager

Gère les quotas CPU/mémoire/disque par client.

**Responsabilités**:
- Tracker ressources par client
- Vérifier quotas avant exécution
- Nettoyer les ressources après subprocess
- Audit trail des dépassements

**Interface**:
```python
class ResourceManager:
    def get_client_quotas(self, client_id: str) -> ClientQuotas:
        """Get resource quotas for client"""

    def check_availability(
        self,
        client_id: str,
        required: ResourceRequirement
    ) -> bool:
        """Check if enough resources available"""

    def allocate(self, client_id: str, resources: ResourceRequirement) -> None:
        """Allocate resources to subprocess"""

    def release(self, client_id: str, pid: int) -> None:
        """Release resources from subprocess"""
```

---

### Component 4: SandboxStateManager

Gère la persistance de l'état sandbox pour un client.

**Responsabilités**:
- Sauvegarder état variables après execution
- Charger état variables avant execution
- Sérialiser/désérialiser via JSON
- Isolation par client

**Interface**:
```python
class SandboxStateManager:
    async def save_state(self, client_id: str, state: Dict) -> None:
        """Save sandbox state to data/clients/{client_id}/state.json"""

    async def load_state(self, client_id: str) -> Dict:
        """Load sandbox state from file"""

    async def clear_state(self, client_id: str) -> None:
        """Clear client sandbox state"""
```

---

## 🔐 Permissions (Phase 6 New)

### Existing Permissions (Phase 2-3)
- `FILE_READ` - Lire fichiers
- `FILE_WRITE` - Écrire fichiers
- `CODE_EXECUTION` - Exécuter du code
- `CODE_EXECUTION_SUDO` - Exécuter avec sudo
- `SYSTEM_COMMAND` - Exécuter commandes système

### New Permissions (Phase 6)
- `FILE_READ_CROSS_CLIENT` - Lire fichiers d'autres clients
- `FILE_WRITE_CROSS_CLIENT` - Écrire fichiers d'autres clients
- `QUOTA_OVERRIDE` - Ignorer les quotas de ressources

---

## 📂 Structure des répertoires

```
/mnt/share/Sources/MCP_server/
├── data/
│   ├── clients/                        # Répertoires isolés par client
│   │   ├── {client_id_1}/
│   │   │   ├── state.json              # Variables sandbox persistantes
│   │   │   ├── files/                  # Fichiers créés par ce client
│   │   │   └── ...
│   │   ├── {client_id_2}/
│   │   │   ├── state.json
│   │   │   └── ...
│   │   └── ...
│   ├── clients.json                    # Phase 3: clients authentifiés
│   ├── tokens.json                     # Phase 3: JWT tokens
│   └── audit.json                      # Phase 3: audit trail
│
├── mcp_server/
│   ├── resources/
│   │   ├── subprocess_executor.py      # Phase 6: Execute code in subprocess
│   │   ├── client_isolation.py         # Phase 6: Client directory isolation
│   │   ├── resource_manager.py         # Phase 6: CPU/Memory/Disk quotas
│   │   └── sandbox_state.py            # Phase 6: Persist sandbox state
│   ├── security/
│   │   └── permission.py               # Updated: Add Phase 6 permissions
│   └── ...
│
└── tests/
    └── test_phase6_integration.py      # Phase 6: Integration tests
```

---

## 🧪 Tests d'Acceptation (Phase 6)

| UC | Test | Expected | Status |
|----|------|----------|--------|
| UC6.1 | Client isolation - read own file | ✅ Succès | pending |
| UC6.1 | Client isolation - read other file | ❌ Permission denied | pending |
| UC6.2 | Subprocess execute - normal | ✅ Code executes, returns result | pending |
| UC6.2 | Subprocess timeout - code sleeps 100s | ❌ Timeout error | pending |
| UC6.2 | Subprocess crash - SEGFAULT | ❌ Crash error | pending |
| UC6.3 | Quota check - within limit | ✅ Executes | pending |
| UC6.3 | Quota check - exceeds limit | ❌ QuotaExceededError | pending |
| UC6.3 | Quota override - permission granted | ✅ Executes (ignores quota) | pending |
| UC6.4 | Sandbox persistence - same client | ✅ Variables persist | pending |
| UC6.4 | Sandbox persistence - new client | ❌ Variables not shared | pending |
| UC6.5 | Cross-client read - no permission | ❌ Permission denied | pending |
| UC6.5 | Cross-client read - with permission | ✅ Can read | pending |
| UC6.6 | Quota override - no permission | ❌ Quota denied | pending |
| UC6.6 | Quota override - with permission | ✅ Quota ignored | pending |

---

## ⏱️ Chronologie de Phase 6

```
Semaine 1:
├── Planification (DONE)
├── Design SubprocessExecutor
├── Implement SubprocessExecutor
└── Unit tests SubprocessExecutor (5-8 tests)

Semaine 2:
├── Design ClientIsolationManager
├── Implement ClientIsolationManager
├── Design ResourceManager
├── Implement ResourceManager
└── Unit tests (10-15 tests)

Semaine 3:
├── Design SandboxStateManager
├── Implement SandboxStateManager
├── Update PermissionManager (new permissions)
├── Update ExecutionManager (use SubprocessExecutor)
└── Unit tests (8-10 tests)

Semaine 4:
├── Integration tests (15-20 tests)
├── Update examples (example_process_isolation.py)
├── Update documentation
└── Commit Phase 6
```

---

## 📊 Métriques de succès Phase 6

| Métrique | Target | Success Criteria |
|----------|--------|------------------|
| Unit tests | 25-30 | All passing ✓ |
| Integration tests | 15-20 | All passing ✓ |
| Client isolation | 100% | Zero cross-client access ✓ |
| Subprocess timeout | 100% | All timeouts work ✓ |
| Resource tracking | 100% | All quotas enforced ✓ |
| Backward compat | 100% | Phase 1-5 tests pass ✓ |

---

**Prêt pour commencer Phase 6?** ✅
