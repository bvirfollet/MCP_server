# Politique de Sécurité - Serveur MCP

## 1. Principes de Sécurité Fondamentaux

### 1.1 Sécurité par Défaut
- Refus par défaut (Deny by Default)
- Permissions explicites requises
- Validation stricte de toutes les entrées
- Logging de tous les accès

### 1.2 Défense en Profondeur
```
Client Request
    ↓ [Layer 1] Authentication
    ↓ [Layer 2] Authorization (Permissions)
    ↓ [Layer 3] Input Validation
    ↓ [Layer 4] Sandboxing
    ↓ [Layer 5] Execution (Limited Capabilities)
    ↓ [Layer 6] Output Validation
    ↓ [Layer 7] Audit Logging
    ↓
Result
```

---

## 2. Modèle de Menaces

### 2.1 Menaces Identifiées

| Menace | Sévérité | Mitigation | Status |
|--------|----------|-----------|--------|
| Client malveillant injecte du code | **CRITIQUE** | Sandboxing + Whitelist | TBD |
| Accès fichiers non autorisés | **CRITIQUE** | Permission Manager + Path validation | TBD |
| Exécution avec privileges excessifs | **CRITIQUE** | Isolation de processus + User/Group separation | TBD |
| DoS par trop de requêtes | **HAUTE** | Rate limiting + Resource limits | TBD |
| Interception des données | **HAUTE** | Chiffrement TLS 1.3 | TBD |
| Escalade de privilèges | **CRITIQUE** | RBAC strict + Audit | TBD |
| Accès non authentifié | **CRITIQUE** | Authentication Manager | TBD |
| Replay attacks | **MOYENNE** | Nonce + Timestamp validation | TBD |

---

## 3. Architecture de Sécurité

### 3.1 Authentification

#### 3.1.1 Schémas Supportés
1. **JWT (JSON Web Tokens)**
   - RS256 signing
   - Expiration courte (15 minutes)
   - Refresh tokens (7 jours)
   - Révocation par blacklist

2. **mTLS (Mutual TLS)**
   - Certificats client et serveur
   - Chaîne de certification validée
   - Révocation par OCSP (futur)

3. **Bearer Tokens**
   - Tokens API longue durée (pour services)
   - Scope limitées
   - Rotation obligatoire

#### 3.1.2 Processus d'Authentification
```python
# Pseudocode
def authenticate_client(credentials):
    # 1. Valider format
    if not is_valid_format(credentials):
        raise AuthenticationError("Invalid format")

    # 2. Extraire et vérifier signature
    payload = verify_signature(credentials, SECRET_KEY)

    # 3. Vérifier non-expiration
    if is_expired(payload['exp']):
        raise AuthenticationError("Token expired")

    # 4. Vérifier pas en blacklist
    if is_revoked(payload['jti']):
        raise AuthenticationError("Token revoked")

    # 5. Loader les permissions associées
    client_id = payload['sub']
    return load_client_permissions(client_id)
```

### 3.2 Autorisation (Permissions)

#### 3.2.1 Types de Permissions
```python
PermissionType = Enum[
    # Fichiers
    'FILE_READ',           # Lire fichiers dans scope
    'FILE_WRITE',          # Écrire fichiers dans scope
    'FILE_DELETE',         # Supprimer fichiers dans scope
    'FILE_WRITE_GLOBAL',   # Écrire hors scope (DANGEREUX)

    # Exécution
    'CODE_EXECUTION',      # Exécuter code Python
    'CODE_EXECUTION_SUDO', # Exécuter avec sudo
    'SYSTEM_COMMAND',      # Exécuter commandes système

    # Réseau
    'NETWORK_OUTBOUND',    # Accès réseau sortant
    'NETWORK_LISTEN',      # Créer serveur réseau

    # Système
    'PROCESS_SPAWN',       # Créer sous-processus
    'PROCESS_KILL',        # Tuer processus

    # Custom
    'CUSTOM_*',            # Permissions personnalisées
]
```

#### 3.2.2 Matrice Permissions
```
Client: "ai_assistant_1"
Permissions:
  - {type: FILE_READ, path: "/app/data/*"}
  - {type: FILE_WRITE, path: "/app/data/output/*"}
  - {type: CODE_EXECUTION, restricted: true}
  - {type: SYSTEM_COMMAND, commands: ["ls", "grep"]}

Client: "trusted_service"
Permissions:
  - {type: FILE_READ, path: "/*"}
  - {type: FILE_WRITE, path: "/*"}
  - {type: CODE_EXECUTION, restricted: false}
  - {type: PROCESS_SPAWN, max_concurrent: 5}
```

#### 3.2.3 Validation de Permission
```python
def check_permission(client: ClientContext,
                     required_permission: Permission) -> bool:
    # 1. Client a-t-il la permission ?
    if not client.has_permission(required_permission.type):
        audit_log("PERMISSION_DENIED", client_id, required_permission)
        return False

    # 2. Est-ce dans les limites de la permission ?
    if required_permission.type == PermissionType.FILE_READ:
        path = required_permission.args.get('path')
        if not is_within_allowed_paths(client, path):
            audit_log("PATH_OUT_OF_SCOPE", client_id, path)
            return False

    # 3. Quota vérifié ?
    if not check_quota(client, required_permission.type):
        audit_log("QUOTA_EXCEEDED", client_id, required_permission.type)
        return False

    return True
```

### 3.3 Isolation (Sandboxing)

#### 3.3.1 Sandbox par Client
Chaque client exécute dans un sandbox isolé :

```
┌─────────────────────────────────────────────┐
│            Client 1 Sandbox                  │
│  ┌─────────────────────────────────────────┐│
│  │ Répertoire: /app/sandbox/client1/       ││
│  │ User: client1_user                       ││
│  │ Permissions: [FILE_READ, CODE_EXECUTION]││
│  │ Resources: CPU 50%, Memory 512MB         ││
│  │ Timeout: 30s par requête                 ││
│  └─────────────────────────────────────────┘│
└─────────────────────────────────────────────┘

┌─────────────────────────────────────────────┐
│            Client 2 Sandbox                  │
│  ┌─────────────────────────────────────────┐│
│  │ Répertoire: /app/sandbox/client2/       ││
│  │ User: client2_user                       ││
│  │ Permissions: [FILE_READ, FILE_WRITE]    ││
│  │ Resources: CPU 30%, Memory 256MB         ││
│  │ Timeout: 60s par requête                 ││
│  └─────────────────────────────────────────┘│
└─────────────────────────────────────────────┘
```

#### 3.3.2 Implémentation Sandbox

**Option 1 : Python Restrictions**
- `sys.modules` whitelist
- `__builtins__` restrictions
- Eval/Exec dans namespace sécurisé

**Option 2 : Processus Séparé**
- Fork subprocess par requête
- User/Group isolation (Linux)
- cgroups pour limiter ressources

**Option 3 : Container (Docker)**
- Alpine image minimale
- Read-only rootfs
- Network isolation

### 3.4 Validation d'Entrée

#### 3.4.1 Règles de Validation
```python
def validate_input(input_data: dict, schema: dict) -> dict:
    """
    Validation stricte de toutes les entrées

    Règles:
    1. Type checking strict
    2. Longueur maximale appliquée
    3. Whitelist de caractères autorisés
    4. Pas de sérialisation non contrôlée
    5. Pas de code exécutable non signé
    """

    errors = []

    for field, value in input_data.items():
        if field not in schema:
            errors.append(f"Unknown field: {field}")
            continue

        spec = schema[field]

        # Type validation
        if not isinstance(value, spec['type']):
            errors.append(f"{field}: expected {spec['type']}, got {type(value)}")

        # Length validation
        if 'max_length' in spec and len(str(value)) > spec['max_length']:
            errors.append(f"{field}: exceeds max length {spec['max_length']}")

        # Pattern validation
        if 'pattern' in spec:
            if not re.match(spec['pattern'], str(value)):
                errors.append(f"{field}: invalid format")

        # Enum validation
        if 'enum' in spec:
            if value not in spec['enum']:
                errors.append(f"{field}: not in allowed values")

    if errors:
        raise ValidationError("; ".join(errors))

    return input_data
```

### 3.5 Audit et Logging

#### 3.5.1 Événements Auditables
```
Authentication:
  - login_success
  - login_failed (with reason)
  - logout
  - token_revoked

Authorization:
  - permission_checked (allow/deny)
  - permission_denied (with reason)
  - quota_exceeded

Execution:
  - tool_called
  - tool_completed
  - tool_failed
  - code_executed

File System:
  - file_read
  - file_written
  - file_deleted
  - path_accessed

Security:
  - exception_raised
  - sandbox_violation
  - rate_limit_exceeded
```

#### 3.5.2 Format de Log
```json
{
  "timestamp": "2025-11-23T15:30:45.123Z",
  "event_type": "tool_called",
  "severity": "INFO",
  "client_id": "ai_assistant_1",
  "request_id": "req_abc123",
  "tool_name": "read_file",
  "parameters": {
    "path": "/app/data/file.txt",
    "redacted": false
  },
  "result": "success",
  "execution_time_ms": 45,
  "source_ip": "192.168.1.100"
}
```

---

## 4. Protection Contre Attaques Courantes

### 4.1 Code Injection
**Risque :** Client exécute du code arbitraire
**Mitigation :**
- Sandbox restrictif (pas d'import de modules système)
- Whitelist d'imports autorisés
- AST parsing pour détecter patterns dangereux
- Exécution avec timeouts

### 4.2 Path Traversal
**Risque :** Client accède à fichiers en dehors du scope
**Mitigation :**
- Résolution canonique de paths (`os.path.realpath`)
- Vérification que chemin est dans scope du client
- Validation de symlinks
- Refus des `..` dans les paths

### 4.3 DoS (Denial of Service)
**Risque :** Client surcharge le serveur
**Mitigation :**
- Rate limiting par client (ex: 100 req/min)
- Timeout d'exécution (ex: 30s max)
- Limite de mémoire (cgroups)
- Limite de fichiers ouverts
- Queue de requêtes avec taille max

### 4.4 Privilege Escalation
**Risque :** Client élève ses privilèges
**Mitigation :**
- Jamais exécuter comme root par défaut
- Utilisateur système dédié par client
- Capability dropping (Linux)
- Audit des tentatives d'escalade

### 4.5 Information Disclosure
**Risque :** Client accède à secrets ou données sensibles
**Mitigation :**
- Redaction des secrets dans logs
- Scope limité d'accès par client
- Séparation des données par client
- Chiffrement at-rest des données sensibles

---

## 5. Conformité et Standards

### 5.1 Conformité OWASP
- ✅ A01: Broken Access Control → RBAC strict
- ✅ A02: Cryptographic Failures → TLS 1.3
- ✅ A03: Injection → Input validation + Sandbox
- ✅ A04: Insecure Design → Secure by default
- ✅ A05: Security Misconfiguration → Defaults sécurisés
- ✅ A06: Vulnerable Components → Audit dépendances
- ✅ A07: Authentication Failures → JWT + mTLS
- ✅ A08: Data Integrity Failures → Signatures
- ✅ A09: Logging Failures → Audit logging
- ✅ A10: SSRF → Réseau isolé

### 5.2 Autres Standards
- RFC 8174 : JWT
- RFC 5246 : TLS 1.2
- RFC 8446 : TLS 1.3
- NIST SP 800-53 : Access Control
- CWE Top 25 : Vulnerable Code Patterns

---

## 6. Processus de Sécurité

### 6.1 Code Review Checklist
- [ ] Pas de hardcoded secrets
- [ ] Validation de toutes les entrées
- [ ] Gestion d'erreurs appropriée
- [ ] Audit logging présent
- [ ] Pas de vulnérabilité OWASP
- [ ] Performance acceptable
- [ ] Tests de sécurité présents

### 6.2 Gestion des Secrets
- [ ] Utiliser variables d'environnement
- [ ] Jamais committer secrets dans Git
- [ ] Rotation régulière des tokens
- [ ] Utiliser Secret Manager (en production)
- [ ] Audit de l'accès aux secrets

### 6.3 Incident Response
```
Découverte d'incident
    ↓
Contention (limiter les dégâts)
    ↓
Investigation (logs, forensics)
    ↓
Remediation (fixer la vulnérabilité)
    ↓
Post-Mortem (leçons apprises)
    ↓
Communication (notification clients)
```

---

## 7. Roadmap Sécurité

| Phase | Fonctionnalité | Priority |
|-------|---------------|----------|
| 1 | Auth (JWT) | **CRITIQUE** |
| 1 | Permissions (RBAC) | **CRITIQUE** |
| 1 | Input Validation | **CRITIQUE** |
| 1 | Audit Logging | **CRITIQUE** |
| 2 | mTLS | **HAUTE** |
| 2 | Rate Limiting | **HAUTE** |
| 2 | Sandbox (processus) | **HAUTE** |
| 3 | OCSP Stapling | MOYENNE |
| 3 | Container Isolation | MOYENNE |
| 4 | Hardware Security Modules | BASSE |

---

*Document créé : 2025-11-23*
*Dernière mise à jour : 2025-11-23*
*Statut : Draft (À améliorer pendant implémentation)*
