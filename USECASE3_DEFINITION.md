# UseCase 3 - Authentification et Persistance

## 📋 Vue d'ensemble

**Phase 3** ajoute l'authentification client et la persistance des données:
- JWT (JSON Web Tokens) pour stateless authentication
- mTLS optionnel pour transport sécurisé
- Persistance JSON locale pour audit trail et tokens
- Client filtering basé sur authentification

**Durée estimée:** 1-2 jours de développement
**Tests ciblés:** 50-60 tests unitaires + intégration

---

## 🎯 Features

### Feature 1: JWT Authentication

```gherkin
Feature: JWT Authentication

  Scenario: Client obtient un token JWT
    Given un client envoie credentials (username/password)
    When le client appelle GET /auth/token
    Then le serveur retourne un JWT valide
    And le JWT contient (client_id, username, exp, iat)
    And le JWT est signé avec la clé secrète du serveur

  Scenario: Client utilise le JWT pour un appel
    Given un client possède un JWT valide
    When le client appelle tools/list avec le JWT
    Then le serveur valide le JWT
    And l'appel est autorisé
    And le client_context est rempli avec les données du JWT

  Scenario: JWT expiré est rejeté
    Given un client possède un JWT expiré
    When le client appelle tools/list avec le JWT expiré
    Then le serveur retourne 401 Unauthorized
    And le client doit se réauthentifier

  Scenario: JWT invalide/corrompu est rejeté
    Given un client possède un JWT corrompu
    When le client appelle tools/list avec le JWT corrompu
    Then le serveur retourne 401 Unauthorized
    And une erreur de validation est loggée

  Scenario: Refresh token étend la session
    Given un client possède un refresh token valide
    When le client appelle POST /auth/refresh avec le refresh token
    Then le serveur retourne un nouveau JWT
    And le nouveau JWT a une nouvelle expiration
    And l'ancien JWT peut toujours être utilisé (grâce au refresh)
```

### Feature 2: Persistance des Tokens

```gherkin
Feature: Persistance des Tokens

  Scenario: Tokens sont stockés localement
    Given le serveur démarre
    When un client se crée un token JWT
    Then le token est enregistré dans tokens.json
    And le fichier contient (token_id, client_id, exp, created_at)

  Scenario: Tokens revoqués ne sont plus valides
    Given un token JWT est enregistré
    When le serveur appelle revoke_token(token_id)
    Then le token est marqué comme révoqué dans tokens.json
    And utiliser ce token retourne 401 Unauthorized

  Scenario: Tokens expirent automatiquement
    Given un token JWT est expiré
    When le serveur vérifie le token
    Then le token n'est plus valide
    And une nouveau token doit être demandé

  Scenario: Tokens survivent au redémarrage du serveur
    Given des tokens sont enregistrés dans tokens.json
    When le serveur redémarre
    Then les tokens sont restaurés en mémoire
    And les tokens expirants sont purges
```

### Feature 3: Audit Trail Persistant

```gherkin
Feature: Audit Trail Persistant

  Scenario: Toutes les exécutions sont loggées
    Given un client exécute un outil
    When execute_tool retourne
    Then un audit entry est créé dans audit.json
    And l'entry contient (timestamp, client_id, tool_name, status, duration)

  Scenario: Échecs d'authentification sont loggés
    Given un client envoie des credentials invalides
    When auth/token est appelé
    Then un audit entry "auth_failed" est créé
    And l'entry contient (client_id, reason, timestamp)

  Scenario: Audit trail persiste
    Given des audit entries sont enregistrées
    When le serveur redémarre
    Then l'audit trail est disponible
    And les données historiques sont intactes

  Scenario: Audit trail peut être consulté
    Given des audit entries sont enregistrées
    When le serveur appelle GET /audit (endpoint optionnel)
    Then retourne les entries récentes
    And supporte filtrage par client_id, date, status
```

### Feature 4: Client Filtering (optionnel Phase 3)

```gherkin
Feature: Client Filtering par Authentification

  Scenario: Clients non authentifiés voient moins d'outils
    Given un client est NOT authentifié
    When appelle tools/list
    Then retourne seulement les outils "public"

  Scenario: Clients authentifiés voient leurs outils
    Given un client est authentifié (JWT valide)
    When appelle tools/list
    Then retourne les outils "public" + ses outils
    And chaque outil inclut ses permissions requises

  Scenario: Admin peut voir tous les outils
    Given un client a le rôle "admin"
    When appelle tools/list
    Then retourne TOUS les outils
    And inclut les permissions requises pour chacun
```

---

## 📊 Critères d'Acceptation

### Authentification
- ✅ JWT generation avec HS256 (HMAC-SHA256)
- ✅ JWT validation avec signature checking
- ✅ Token expiration (configurable, défaut 1 heure)
- ✅ Refresh tokens (défaut 7 jours)
- ✅ Token revocation support

### Persistance
- ✅ tokens.json pour enregistrer les tokens
- ✅ audit.json pour enregistrer les exécutions
- ✅ clients.json pour stocker les credentials
- ✅ Restauration au redémarrage du serveur
- ✅ Auto-cleanup des tokens expirants

### Intégration
- ✅ MCPServer accepte tokens JWT dans les requêtes
- ✅ Token validation middleware
- ✅ ClientContext enrichi avec user info
- ✅ Audit trail pour chaque exécution
- ✅ Backward compatible avec Phase 2 (sans token)

### Tests
- ✅ 50+ tests unitaires
- ✅ Tests JWT generation/validation
- ✅ Tests expiration
- ✅ Tests persistence/restore
- ✅ Tests intégration avec MCPServer

### Documentation
- ✅ ARCHITECTURE_PHASE3.md
- ✅ Mise à jour README.md
- ✅ Mise à jour CHANGELOG.md
- ✅ Exemples d'utilisation

---

## 🏗️ Architecture Phase 3

### Couches ajoutées

```
MCPServer (Phase 1)
    ↓
ToolManager + PermissionManager (Phase 2)
    ↓
ExecutionManager + SandboxContext (Phase 2)
    ↓
└─→ AuthenticationManager (NEW)  ← JWT generation/validation
    └─→ TokenManager (NEW)       ← Token persistence
    └─→ AuditLogger (NEW)        ← Audit trail persistence
    └─→ ClientManager (NEW)      ← Client credentials
```

### Fichiers à créer

```
mcp_server/
├── security/
│   ├── authentication/          (NEW)
│   │   ├── jwt_handler.py       (NEW) - JWT generation/validation
│   │   ├── token_manager.py     (NEW) - Token persistence
│   │   └── client_manager.py    (NEW) - Client credentials
│   │
│   └── audit/                   (NEW)
│       └── audit_logger.py      (NEW) - Audit trail persistence
│
└── persistence/                 (NEW)
    ├── json_store.py            (NEW) - JSON file handling
    ├── tokens.json              (NEW DATA)
    ├── audit.json               (NEW DATA)
    └── clients.json             (NEW DATA)
```

### Modifications existantes

```
core/mcp_server.py
    └─ Ajouter auth middleware
    └─ Ajouter endpoints: /auth/token, /auth/refresh, /auth/revoke

security/client_context.py
    └─ Ajouter fields: user_id, username, roles, auth_time
    └─ Ajouter JWT claim extraction

protocol/mcp_protocol_handler.py
    └─ Ajouter extraction JWT du header Authorization
    └─ Ajouter validation middleware
```

---

## 📋 Plan d'implémentation

### Phase 3.1 - JWT & Token Management
1. JWTHandler - génération/validation JWT
2. TokenManager - persistance tokens.json
3. ClientManager - gestion credentials
4. Tests unitaires (20+ tests)

### Phase 3.2 - Audit Trail
1. AuditLogger - enregistrement audit.json
2. Intégration avec ExecutionManager
3. Tests unitaires (15+ tests)

### Phase 3.3 - MCPServer Integration
1. Middleware authentification
2. Nouveaux endpoints (/auth/...)
3. Tests d'intégration (15+ tests)

### Phase 3.4 - Documentation
1. ARCHITECTURE_PHASE3.md
2. Mise à jour README/CHANGELOG
3. Exemples JWT
4. Guide de déploiement

---

## 🔐 Sécurité

### JWT Secrets
- HS256 (HMAC-SHA256) avec clé secrète 32+ caractères
- Clé stockée en variable d'environnement ou config
- Rotation de clé supportée (Phase 4)

### Token Management
- Tokens révocables (blacklist en mémoire + persistance)
- Expiration stricte
- Refresh tokens avec expiration plus longue

### Credentials
- Stockés en bcrypt hashe (NOT plaintext)
- Fichier clients.json protégé (permissions 0600)

### Audit Trail
- Immuable (append-only)
- Contient qui, quand, quoi
- Format JSON structuré

---

## 📈 Métriques

**Tests ciblés:** 50-60 tests
- JWTHandler: 15 tests
- TokenManager: 15 tests
- ClientManager: 10 tests
- AuditLogger: 10 tests
- Integration: 15 tests

**Code:** ~1,200 lignes
**Documentation:** ~300 lignes
**Configuration JSON:** 3 fichiers

---

## ✅ Définition de "Done"

- [ ] 60 tests passants (Phase 3)
- [ ] 209 tests cumulatifs (Phase 1+2+3)
- [ ] ARCHITECTURE_PHASE3.md écrit
- [ ] README/CHANGELOG mis à jour
- [ ] Client d'exemple avec JWT
- [ ] Tous les merge conflicts résolus
- [ ] Git commits propres
- [ ] Documentation complète
