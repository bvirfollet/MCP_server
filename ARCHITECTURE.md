# Architecture du Serveur MCP - Documentation

## 1. Vue d'ensemble

Serveur MCP (Model Context Protocol) en Python pur, permettant aux IA du marché (Claude, GPT, Gemini) d'interagir avec l'ordinateur local de manière sécurisée et contrôlée.

**Principes fondamentaux :**
- Architecture modulaire et extensible
- Séparation des responsabilités (Architecture 3-tiers)
- 1 classe par fichier
- Tests unitaires intégrés dans chaque fichier
- Sécurité informatique comme aspect critique
- Support de multiples protocoles de transport

---

## 2. Architecture Générale - Modèle 3-tiers

```
┌─────────────────────────────────────────────────────┐
│                   LAYER 1 : TRANSPORT               │
│     (Stdio/JSON-RPC, TCP/HTTP+WebSocket, DBus)      │
└─────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────┐
│               LAYER 2 : PROTOCOL & ROUTING          │
│  (MCP Protocol Handler, Request Router, Dispatcher) │
└─────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────┐
│          LAYER 3 : BUSINESS LOGIC & SECURITY        │
│  (Permission Manager, Tool Manager, Client Manager) │
└─────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────┐
│         LAYER 4 : RESOURCES & INTEGRATION           │
│  (File System, Shell Execution, System Resources)   │
└─────────────────────────────────────────────────────┘
```

---

## 3. Composants Principaux

### 3.1 Couche Transport (Layer 1)

| Composant | Responsabilité | Ordre de Développement |
|-----------|-----------------|------------------------|
| **StdioTransport** | Communication JSON-RPC via stdin/stdout | 1er |
| **TCPTransport** | Communication HTTP+WebSocket | 2ème |
| **DBusTransport** | Communication DBus Linux | 3ème |

### 3.2 Couche Protocole & Routage (Layer 2)

| Composant | Responsabilité |
|-----------|-----------------|
| **MCPProtocolHandler** | Gestion du protocole MCP 2024-11 |
| **RequestRouter** | Routage des requêtes vers les handlers |
| **CapabilitiesManager** | Exposition des capabilities du serveur |

### 3.3 Couche Logique Métier & Sécurité (Layer 3)

| Composant | Responsabilité |
|-----------|-----------------|
| **PermissionManager** | Gestion des permissions par client et par type |
| **ClientManager** | Gestion des clients connectés et isolation |
| **ToolManager** | Enregistrement et exposition des tools |
| **AuditLogger** | Traçabilité complète des opérations |
| **AuthenticationManager** | Authentification des clients |

### 3.4 Couche Ressources (Layer 4)

| Composant | Responsabilité |
|-----------|-----------------|
| **FileSystemManager** | Accès sécurisé au système de fichiers |
| **ExecutionManager** | Exécution de code avec isolation |
| **SandboxManager** | Gestion des espaces cloisonnés par client |

---

## 4. Système de Sécurité

### 4.1 Types de Permissions

```
PermissionType:
  ├── FILE_READ (Lecture fichier)
  ├── FILE_WRITE (Écriture fichier)
  ├── FILE_WRITE_GLOBAL (Écriture hors scope)
  ├── CODE_EXECUTION (Exécution de code)
  ├── CODE_EXECUTION_SUDO (Exécution superuser)
  ├── SYSTEM_COMMAND (Exécution système)
  └── CUSTOM_* (Permissions personnalisées)
```

### 4.2 Modèle d'Isolation

Chaque client dispose d'un espace cloisonné (Sandbox) :
- Répertoire de travail dédié
- Contexte d'exécution isolé
- Ensemble de permissions spécifiques
- Limite de ressources (CPU, mémoire, fichiers)

### 4.3 Chaîne de Sécurité

```
Client Request
    ↓
[1] Authentication Check
    ↓
[2] Permission Validation
    ↓
[3] Sandbox Validation
    ↓
[4] Tool Execution
    ↓
[5] Audit Logging
    ↓
Response
```

---

## 5. Flux d'Intégration d'un Module Externe

Les modules Python qui utilisent cette librairie doivent :

1. **Déclarer les tools** :
```python
module.register_tool(
    name="my_tool",
    description="...",
    input_schema={...},
    permissions=[
        Permission(PermissionType.FILE_READ, "*.txt"),
        Permission(PermissionType.CODE_EXECUTION, restricted=False)
    ]
)
```

2. **Implémenter les handlers** :
```python
async def handle_my_tool(client: ClientContext, params: dict) -> dict:
    # Exécuter la logique
    pass
```

3. **Enregistrer auprès du serveur** :
```python
server.register_module(my_module)
```

---

## 6. Structure des Fichiers

```
mcp_server/
├── __init__.py
├── core/
│   ├── __init__.py
│   ├── mcp_server.py              # Classe serveur principale
│   └── constants.py               # Constantes globales
├── transport/
│   ├── __init__.py
│   ├── base_transport.py           # Classe abstraite Transport
│   ├── stdio_transport.py          # Implémentation JSON-RPC
│   ├── tcp_transport.py            # Implémentation TCP/HTTP+WS
│   └── dbus_transport.py           # Implémentation DBus
├── protocol/
│   ├── __init__.py
│   ├── mcp_protocol_handler.py     # Handler MCP
│   └── request_router.py           # Routeur de requêtes
├── security/
│   ├── __init__.py
│   ├── permission_manager.py       # Gestion des permissions
│   ├── authentication_manager.py   # Authentification
│   ├── audit_logger.py             # Audit et logging
│   └── client_context.py           # Contexte client isolé
├── tools/
│   ├── __init__.py
│   └── tool_manager.py             # Gestion des tools
├── resources/
│   ├── __init__.py
│   ├── filesystem_manager.py       # Accès fichiers sécurisé
│   ├── execution_manager.py        # Exécution de code
│   └── sandbox_manager.py          # Gestion sandboxes
└── tests/
    ├── __init__.py
    ├── test_*.py                   # Tests unitaires
    └── integration_tests/          # Tests d'intégration
```

---

## 7. Protocole MCP 2024-11

Le serveur implémente le protocole MCP 2024-11 avec :
- JSON-RPC 2.0 comme base
- Support des notifications asynchrones
- Support des ressources
- Support des prompts
- Support des tools (principal focus)

---

## 8. Stratégies de Sécurité Détaillées

### 8.1 Authentification
- Token-based (JWT)
- Mutual TLS pour transports réseau
- Signature des requêtes

### 8.2 Chiffrement
- TLS 1.3 pour TCP/HTTP
- Chiffrement optionnel pour DBus
- Intégrité des messages garantie

### 8.3 Audit
- Logging centralisé de toutes les opérations
- Format structuré (JSON)
- Immuabilité des logs (append-only)

### 8.4 Isolation
- Processus séparé par client (optionnel)
- Limite de ressources via cgroups (Linux)
- Timeouts d'exécution

---

## 9. Phases de Développement

| Phase | UseCase | Composants | Dépendances |
|-------|---------|-----------|-------------|
| 1 | Initialisation & Health | StdioTransport, MCPProtocolHandler | Aucune |
| 2 | Enregistrement Tools | ToolManager, PermissionManager | Phase 1 |
| 3 | Exécution Tools | ExecutionManager, SandboxManager | Phase 2 |
| 4 | Authentification | AuthenticationManager | Phase 1 |
| 5 | TCP Transport | TCPTransport | Phase 1, 4 |
| 6 | DBus Transport | DBusTransport | Phase 1, 4 |
| 7 | Audit complet | AuditLogger | Toutes |

---

## 10. Considérations de Performance

- Asynchrone (asyncio) pour scalabilité
- Connection pooling
- Lazy loading des modules
- Cache des permissions
- Compression optionnelle des réponses

---

## 11. Conformité et Standards

- Conforme MCP 2024-11
- Conforme OWASP Top 10
- Logging conforme RFC 5424
- Chiffrement conforme NIST

---

*Document créé : 2025-11-23*
*Dernière mise à jour : 2025-11-23*
