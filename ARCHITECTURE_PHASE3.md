# Architecture Phase 3 - Authentification et Persistance

## 📋 Résumé Exécutif

**Phase 3** ajoute l'authentification stateless via JWT et la persistance des données via JSON local:

| Aspect | Solution |
|--------|----------|
| **Authentification** | JWT (HS256) + Refresh Tokens |
| **Persistence** | JSON local (tokens.json, audit.json, clients.json) |
| **Transport** | Stdio + (mTLS optionnel Phase 4) |
| **Scalabilité** | Single-machine (réplication Phase 5+) |
| **Sécurité** | bcrypt pour credentials, JWT signatures, audit trail |

---

## 🏗️ Architecture Logique

### Flux Authentification

```
┌─────────────────────────────────────────────────┐
│ 1. Client envoie credentials (username/password)│
└──────────────┬──────────────────────────────────┘
               ↓
┌──────────────────────────────────────────────────────┐
│ 2. ClientManager valide contre clients.json (bcrypt)│
└──────────────┬─────────────────────────────────────┘
               ↓
┌──────────────────────────────────────────────────────┐
│ 3. JWTHandler génère JWT + Refresh Token            │
└──────────────┬─────────────────────────────────────┘
               ↓
┌──────────────────────────────────────────────────────┐
│ 4. TokenManager enregistre dans tokens.json          │
└──────────────┬─────────────────────────────────────┘
               ↓
┌──────────────────────────────────────────────────────┐
│ 5. Retourner {access_token, refresh_token, expires} │
└──────────────────────────────────────────────────────┘

Utilisation du JWT:
┌─────────────────────────────────────────────┐
│ Client envoie: Authorization: Bearer <JWT> │
└──────────────┬──────────────────────────────┘
               ↓
┌──────────────────────────────────────────────┐
│ MCPServer extrait JWT du header              │
└──────────────┬───────────────────────────────┘
               ↓
┌──────────────────────────────────────────────┐
│ JWTHandler valide signature + expiration     │
└──────────────┬───────────────────────────────┘
               ↓
┌──────────────────────────────────────────────┐
│ Extraire claims → enrich ClientContext      │
└──────────────┬───────────────────────────────┘
               ↓
┌──────────────────────────────────────────────┐
│ AuditLogger enregistre l'exécution           │
└──────────────────────────────────────────────┘
```

---

## 🔐 Détails Techniques

### JWT (JSON Web Token)

#### Structure
```
Header.Payload.Signature

Header:
{
  "alg": "HS256",
  "typ": "JWT"
}

Payload:
{
  "sub": "client_id",          # Subject (client identifier)
  "username": "alice",          # Username
  "roles": ["user"],            # Roles pour future filtering
  "iat": 1234567890,           # Issued at (timestamp)
  "exp": 1234571490,           # Expiration (défaut +1h)
  "jti": "token_id_123"        # JWT ID (pour revocation)
}

Signature:
HMAC-SHA256(
  base64UrlEncode(header) + "." + base64UrlEncode(payload),
  secret_key
)
```

#### Timing
- **Access Token (JWT):** Expire après 1 heure
- **Refresh Token:** Expire après 7 jours
- **Session:** Peut être étendue avec refresh token

### Token Manager

#### Fichier: tokens.json
```json
{
  "tokens": [
    {
      "jti": "token_id_123",
      "client_id": "client_uuid_456",
      "username": "alice",
      "access_token_hash": "sha256(...)",
      "refresh_token_hash": "sha256(...)",
      "created_at": "2025-11-23T17:00:00Z",
      "access_expires_at": "2025-11-23T18:00:00Z",
      "refresh_expires_at": "2025-11-30T17:00:00Z",
      "revoked": false,
      "revoked_at": null
    }
  ],
  "last_cleanup": "2025-11-23T17:00:00Z"
}
```

#### Opérations
- **Create:** Générer + enregistrer token
- **Validate:** Vérifier signature + expiration + revocation
- **Refresh:** Créer nouveau JWT avec ancien refresh token
- **Revoke:** Marquer token comme révoqué
- **Cleanup:** Supprimer tokens expirants (async, toutes les heures)

### Client Manager

#### Fichier: clients.json
```json
{
  "clients": [
    {
      "client_id": "client_uuid_123",
      "username": "alice",
      "password_hash": "bcrypt(password, salt=10)",
      "email": "alice@example.com",
      "roles": ["user"],
      "created_at": "2025-11-01T00:00:00Z",
      "last_login": "2025-11-23T17:00:00Z",
      "enabled": true,
      "metadata": {
        "department": "engineering"
      }
    }
  ]
}
```

#### Opérations
- **Create:** Ajouter nouveau client (bcrypt password)
- **Authenticate:** Valider credentials (bcrypt check)
- **Get:** Récupérer info client
- **Update:** Mettre à jour metadata
- **Delete:** Supprimer client
- **List:** Lister tous les clients (admin only)

### Audit Logger

#### Fichier: audit.json
```json
{
  "entries": [
    {
      "timestamp": "2025-11-23T17:00:00.123456Z",
      "event_type": "tool_executed",
      "client_id": "client_uuid_456",
      "username": "alice",
      "tool_name": "greet",
      "status": "success",
      "duration_ms": 42,
      "parameters": {"name": "Alice"},
      "result": {"greeting": "Salut Alice!"},
      "error": null,
      "ip_address": null
    },
    {
      "timestamp": "2025-11-23T17:00:30.000000Z",
      "event_type": "auth_success",
      "client_id": "client_uuid_456",
      "username": "alice",
      "token_jti": "token_id_123",
      "status": "success",
      "error": null
    },
    {
      "timestamp": "2025-11-23T17:00:45.000000Z",
      "event_type": "auth_failed",
      "username": "bob",
      "status": "failure",
      "reason": "invalid_credentials",
      "error": "Password mismatch"
    }
  ]
}
```

#### Event Types
- **auth_success:** Client authentifié
- **auth_failed:** Échec authentification
- **auth_token_refresh:** Token rafraîchi
- **auth_token_revoked:** Token révoqué
- **tool_executed:** Outil exécuté (success/error/timeout/permission_denied)
- **permission_denied:** Permission refusée
- **client_created:** Nouveau client créé
- **client_deleted:** Client supprimé

---

## 📁 Structures de Fichiers

### Répertoire persistence/

```
mcp_server/persistence/
├── __init__.py
├── json_store.py          # Base class pour JSON handling
├── token_store.py         # TokenManager
├── client_store.py        # ClientManager
├── audit_store.py         # AuditLogger
└── models.py              # Dataclasses pour serialization
```

### Répertoire security/authentication/

```
mcp_server/security/authentication/
├── __init__.py
├── jwt_handler.py         # JWT generation/validation
├── password.py            # bcrypt wrapper
└── errors.py              # Authentication exceptions
```

### Répertoire données (root)

```
mcp-server/
├── data/                  # Nouvelle répertoire
│   ├── .gitignore        # Exclure *.json de git
│   ├── tokens.json       # Tokens actuellement valides
│   ├── audit.json        # Audit trail (append-only)
│   └── clients.json      # Client credentials + metadata
```

---

## 🔄 Intégration avec Phase 2

### ClientContext enrichi

```python
@dataclass
class ClientContext:
    # Phase 1
    client_id: str
    created_at: datetime
    request_count: int

    # Phase 3 (NEW)
    user_id: Optional[str] = None
    username: Optional[str] = None
    roles: List[str] = field(default_factory=list)
    auth_time: Optional[datetime] = None
    token_jti: Optional[str] = None
    authenticated: bool = False
```

### MCPServer modifications

```python
class MCPServer:
    def __init__(self, ...):
        # Existing Phase 2
        self.tool_manager = ToolManager()
        self.permission_manager = PermissionManager()
        self.execution_manager = ExecutionManager(...)

        # NEW Phase 3
        self.jwt_handler = JWTHandler(secret_key)
        self.token_manager = TokenManager(data_dir)
        self.client_manager = ClientManager(data_dir)
        self.audit_logger = AuditLogger(data_dir)
```

### Middleware authentification

```python
async def _authenticate_request(self, client_ctx, message):
    # 1. Extraire JWT du header Authorization
    token = self._extract_jwt(message)

    if token:
        # 2. Valider JWT
        claims = self.jwt_handler.verify(token)

        # 3. Enrichir ClientContext
        client_ctx.user_id = claims['sub']
        client_ctx.username = claims['username']
        client_ctx.authenticated = True

        # 4. Logger authentification
        self.audit_logger.log_auth_success(...)
    else:
        # Client non authentifié (optionnel, backward compatible)
        self.audit_logger.log_auth_skipped(...)
```

---

## 📊 Fichiers JSON - Format & Permissions

### tokens.json
- **Créé:** Premier run du serveur
- **Permissions:** 0600 (rw-------)
- **Taille:** Peut croître (cleanup régulier)
- **Format:** JSON structuré (array of objects)

### clients.json
- **Créé:** Manuellement ou admin API
- **Permissions:** 0600 (rw-------)
- **Taille:** Petit (centaines d'entrées max)
- **Format:** JSON structuré (array of objects)

### audit.json
- **Créé:** Premier run du serveur
- **Permissions:** 0640 (rw-r-----)
- **Taille:** Croît (archivage Phase 4+)
- **Format:** Append-only (nouvelles entrées toujours en fin)

---

## 🔐 Sécurité

### Secrets & Configuration

```python
# Dans environment ou config
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "changeme-32-chars-minimum")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60
REFRESH_TOKEN_EXPIRE_DAYS = 7
BCRYPT_ROUNDS = 10  # Cost factor
DATA_DIR = "./data"  # Doit être sécurisé (0700)
```

### Sécurité des fichiers

```bash
# Structure répertoires
data/
├── permissions: drwx------ (0700 - owner only)
├── tokens.json: -rw------- (0600)
├── clients.json: -rw------- (0600)
└── audit.json: -rw-r----- (0640 - readable by logs reader)
```

### Validation

- **JWT:** Signature HS256 stricte
- **Password:** bcrypt avec 10 rounds (cost)
- **Token:** Blacklist de revocation (in-memory + persistence)
- **Expiration:** Timezone-aware (UTC)

---

## 🧪 Plan de Tests

### JWTHandler (15 tests)
- [ ] Generate token avec claims corrects
- [ ] Verify token valide
- [ ] Reject token expiré
- [ ] Reject token mal signé
- [ ] Refresh token génère nouveau JWT
- [ ] Claims extraction
- [ ] Timezone handling (UTC)
- [ ] Edge cases (empty claims, etc)

### TokenManager (15 tests)
- [ ] Create/save token
- [ ] Load/verify token
- [ ] Revoke token
- [ ] Token persist sur disk
- [ ] Cleanup tokens expirants
- [ ] Blacklist checking
- [ ] Concurrent access handling

### ClientManager (10 tests)
- [ ] Create/save client
- [ ] Authenticate (valid credentials)
- [ ] Authenticate (invalid password)
- [ ] Authenticate (user not found)
- [ ] bcrypt hashing
- [ ] Load/get client
- [ ] Update metadata

### AuditLogger (10 tests)
- [ ] Log event avec timestamp
- [ ] Persist to disk
- [ ] Append-only behavior
- [ ] Query by client_id
- [ ] Query by event_type
- [ ] Date range filtering

### Integration (15 tests)
- [ ] Full auth flow (credentials → JWT → tool call)
- [ ] Token refresh flow
- [ ] Token revocation
- [ ] ClientContext enrichment
- [ ] Backward compatibility (sans token)
- [ ] Error handling and logging

---

## 📈 Décisions d'Architecture

| Décision | Justification |
|----------|--------------|
| **JWT** | Stateless, pas de session server-side, scalable |
| **HS256** | Simple, crypto standard, suffisant pour usage interne |
| **JSON local** | Zéro dépendances DB, portable, versionnable (sauf data/) |
| **bcrypt** | Standard de facto pour password hashing |
| **Append-only audit** | Immuable, historique complet, forensics-friendly |
| **Refresh tokens** | Permet rotation secrets, session expiration courte |
| **In-memory cache** | Performance (évite disk I/O à chaque request) |
| **Sync serialization** | Simplifie migration Phase 1→2→3 |

---

## 🚀 Roadmap Future

### Phase 3.5 (Optionnel)
- [ ] mTLS support (certificate-based auth)
- [ ] API endpoint pour admin (create/delete clients)
- [ ] Password reset flow
- [ ] 2FA/MFA support

### Phase 4
- [ ] Persistance PostgreSQL
- [ ] Audit log archiving
- [ ] Distributed sessions
- [ ] Key rotation

### Phase 5
- [ ] OAuth2/OIDC support
- [ ] Service-to-service auth
- [ ] Fine-grained audit filtering
- [ ] Real-time audit dashboard

---

## ✅ Definition of Ready

Avant de coder Phase 3:

- [x] UseCase écrit avec features Gherkin
- [x] Architecture documentée
- [x] Fichiers JSON schemas définis
- [x] API endpoints spécifiés
- [x] Tests cases listés
- [x] Sécurité revue

**Statut:** ✅ PRÊT À IMPLÉMENTER
