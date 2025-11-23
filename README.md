# Serveur MCP (Model Context Protocol)

Un serveur MCP sécurisé et modulaire en Python pur, permettant aux modèles d'IA (Claude, GPT, Gemini) d'interagir avec votre ordinateur de manière contrôlée et sécurisée.

## 🎯 Vue d'ensemble

Le serveur MCP expose des "tools" (outils) que les modèles d'IA peuvent appeler pour :
- Lire/écrire des fichiers
- Exécuter du code ou des commandes système
- Interagir avec des ressources système
- Accéder à des services personnalisés

**Avec une sécurité stricte :**
- Authentification des clients (JWT, mTLS)
- Permissions granulaires par client
- Isolation en sandboxes
- Audit complet de toutes les opérations

## 📦 Démarrage Rapide

### Prérequis
- Python 3.10+
- Git (optionnel)

### Installation
```bash
# Cloner le repo
git clone https://github.com/yourusername/mcp-server.git
cd mcp-server

# Installer les dépendances de base
pip install -r requirements.txt

# Installer les dépendances de développement
pip install -r requirements-dev.txt
```

### Utilisation Simple

#### Exemple basique (Phase 1)
```python
from mcp_server import MCPServer

# Créer le serveur
server = MCPServer()

# Ajouter un simple tool
@server.tool(
    name="hello",
    description="Salue quelqu'un",
    input_schema={
        "type": "object",
        "properties": {"name": {"type": "string"}},
        "required": ["name"]
    }
)
async def hello_tool(ctx, params):
    name = params.get("name", "World")
    return {"greeting": f"Bonjour {name}!"}

# Démarrer le serveur
if __name__ == "__main__":
    server.run()
```

#### Exemple avec permissions (Phase 2)
```python
from mcp_server import MCPServer
from mcp_server.security.permission import Permission, PermissionType

# Créer le serveur
server = MCPServer()

# Outil simple (sans permission)
@server.tool(
    name="greet",
    description="Salue quelqu'un",
    input_schema={"properties": {"name": {"type": "string"}}, "required": ["name"]}
)
async def greet(ctx, params):
    name = params.get("name")
    return {"message": f"Salut {name}!"}

# Outil avec permission FILE_READ
@server.tool(
    name="read_file",
    description="Lit un fichier",
    input_schema={"properties": {"path": {"type": "string"}}, "required": ["path"]},
    permissions=[Permission(PermissionType.FILE_READ, "/app/data/*")]
)
async def read_file(ctx, params):
    path = params.get("path")
    return {"content": f"Contenu de {path}"}

# Démarrer le serveur
if __name__ == "__main__":
    server.run()
```

### Voir aussi
- **[Démonstration Phase 2](./examples/README.md)** - Client MCP complet avec permissions
- Exécutez `python examples/example_client.py` pour voir une démo en action

## 📚 Documentation

- **[ARCHITECTURE.md](./ARCHITECTURE.md)** - Architecture générale et composants
- **[IMPLEMENTATION_STRATEGY.md](./IMPLEMENTATION_STRATEGY.md)** - Processus de développement
- **[SECURITY.md](./SECURITY.md)** - Politique et architecture de sécurité
- **[API.md](./docs/API.md)** - Référence API complète (à venir)
- **[DEVELOPER_GUIDE.md](./docs/DEVELOPER_GUIDE.md)** - Guide pour développeurs (à venir)

## 🏗️ Structure du Projet

```
mcp_server/
├── README.md                       # Ce fichier
├── ARCHITECTURE.md                 # Architecture générale
├── IMPLEMENTATION_STRATEGY.md      # Plan de développement
├── SECURITY.md                     # Politique de sécurité
├── CHANGELOG.md                    # Historique des changements
├── pyproject.toml                  # Configuration du projet
├── requirements.txt                # Dépendances
├── requirements-dev.txt            # Dépendances développement
│
├── mcp_server/                     # Code source principal
│   ├── __init__.py
│   ├── core/                       # Cœur du serveur
│   │   ├── mcp_server.py          # Classe serveur principale
│   │   └── constants.py           # Constantes globales
│   ├── transport/                  # Protocoles de transport
│   │   ├── base_transport.py      # Classe abstraite
│   │   ├── stdio_transport.py     # JSON-RPC (stdio)
│   │   ├── tcp_transport.py       # TCP/HTTP+WebSocket
│   │   └── dbus_transport.py      # DBus Linux
│   ├── protocol/                   # Protocole MCP
│   │   ├── mcp_protocol_handler.py
│   │   └── request_router.py
│   ├── security/                   # Sécurité
│   │   ├── permission_manager.py
│   │   ├── authentication_manager.py
│   │   ├── audit_logger.py
│   │   └── client_context.py
│   ├── tools/                      # Gestion des tools
│   │   └── tool_manager.py
│   └── resources/                  # Ressources système
│       ├── filesystem_manager.py
│       ├── execution_manager.py
│       └── sandbox_manager.py
│
├── tests/                          # Tests
│   ├── __init__.py
│   ├── test_integration.py        # Tests d'intégration
│   └── fixtures/                  # Données de test
│
├── docs/                           # Documentation supplémentaire
│   ├── API.md                     # Référence API
│   ├── DEVELOPER_GUIDE.md         # Guide développeurs
│   └── EXAMPLES.md                # Exemples d'utilisation
│
└── .github/
    └── workflows/                  # CI/CD (GitHub Actions)
```

## 🚀 Phases de Développement

| Phase | Objectif | Status |
|-------|----------|--------|
| **1** | Démarrage serveur, protocole MCP de base, transport Stdio | ✅ Complet (73 tests) |
| **2** | Enregistrement et exécution de tools, permissions RBAC, sandbox | ✅ Complet (76 tests) |
| **2.5** | Safe namespace pour code execution (optionnel) | ⏳ À venir |
| **3** | Système d'authentification complet (JWT, mTLS) | ⏳ À venir |
| **4** | Transport TCP/HTTP+WebSocket | ⏳ À venir |
| **5** | Transport DBus | ⏳ À venir |
| **6** | Isolation par processus (subprocess) | ⏳ À venir |
| **7** | Audit et monitoring avancé | ⏳ À venir |

### 📊 Statistiques de Validation

**Phase 1 ✅**
- 6 modules : Transport, Protocol, Client Context, Constants, MCPServer
- 73 tests unitaires passants
- Architecte 3-tiers complète

**Phase 2 ✅**
- 6 modules : Permission, Tool, ToolManager, PermissionManager, ExecutionManager, SandboxContext
- 76 tests unitaires passants
- Système RBAC complet avec audit trail
- Per-client sandbox contexts avec persistance variables
- Exécution sécurisée avec timeouts et validation
- **Total : 149 tests ✓ PASSED**

## 🔒 Sécurité

La sécurité est un aspect **critique** de ce projet.

### Principes Clés
- ✅ **Refus par défaut** - Les permissions doivent être explicitement accordées
- ✅ **Audit complet** - Toutes les opérations sont enregistrées
- ✅ **Isolation** - Chaque client opère dans un sandbox
- ✅ **Validation stricte** - Toutes les entrées sont validées
- ✅ **Chiffrement** - TLS 1.3 pour les transports réseau

### Types de Permissions
- `FILE_READ` - Lire des fichiers
- `FILE_WRITE` - Écrire des fichiers
- `FILE_WRITE_GLOBAL` - Écrire en dehors du scope (dangereux)
- `CODE_EXECUTION` - Exécuter du code Python
- `CODE_EXECUTION_SUDO` - Exécuter avec sudo
- `SYSTEM_COMMAND` - Exécuter des commandes système

Pour plus de détails, voir [SECURITY.md](./SECURITY.md).

## 📝 Exemple : Créer un Module MCP

```python
# my_module.py
from mcp_server import Tool, PermissionType, Permission

# Déclarer les tools
class FileReaderTool(Tool):
    """Tool pour lire des fichiers"""

    name = "read_file"
    description = "Lire le contenu d'un fichier"

    input_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Chemin du fichier"}
        },
        "required": ["path"]
    }

    required_permissions = [
        Permission(PermissionType.FILE_READ, path="*.txt")
    ]

    async def execute(self, client, params):
        path = params.get("path")
        with open(path, 'r') as f:
            return {"content": f.read()}


# Enregistrer le module
def register_module(server):
    server.register_tool(FileReaderTool())


# Dans votre code principal :
# from my_module import register_module
# server = MCPServer()
# register_module(server)
```

## 🧪 Tests

### Exécuter les tests unitaires
```bash
# Tous les tests
python -m unittest discover

# Tests spécifiques
python -m unittest tests.test_authentication
```

### Exécuter les tests d'intégration
```bash
python -m pytest tests/test_integration.py -v
```

### Couverture de tests
```bash
coverage run -m unittest discover
coverage report
coverage html  # Rapport HTML dans htmlcov/
```

## 📊 Architecture Haute Niveau

```
┌─────────────────────────────────────────────────────────┐
│         Client IA (Claude, GPT, Gemini)                 │
└──────────────────────┬──────────────────────────────────┘
                       │
          ┌────────────┴────────────┐
          │                         │
    ┌─────▼──────────────┐   ┌─────▼──────────────┐
    │ Stdio (JSON-RPC)   │   │ TCP/WebSocket      │
    └─────┬──────────────┘   └─────┬──────────────┘
          │                         │
          └────────────┬────────────┘
                       │
        ┌──────────────▼──────────────┐
        │   MCP Protocol Handler      │
        │   Request Router            │
        └──────────────┬──────────────┘
                       │
        ┌──────────────▼──────────────┐
        │  Security Layer             │
        │  - Authentication           │
        │  - Authorization (RBAC)     │
        │  - Audit Logging            │
        └──────────────┬──────────────┘
                       │
        ┌──────────────▼──────────────┐
        │  Tool Manager               │
        │  - Tool Registry            │
        │  - Parameter Validation     │
        └──────────────┬──────────────┘
                       │
        ┌──────────────▼──────────────┐
        │  Execution Manager          │
        │  - Sandboxing               │
        │  - Resource Limiting        │
        │  - Error Handling           │
        └──────────────┬──────────────┘
                       │
        ┌──────────────▼──────────────┐
        │  Resources                  │
        │  - File System              │
        │  - Process Execution        │
        │  - System Calls             │
        └──────────────────────────────┘
```

## 🤝 Contribution

Ce projet suit une méthodologie AGILE stricte :

1. **Définir le UseCase** et les tests d'acceptation
2. **Poser des questions** pour clarifier les concepts
3. **Concevoir l'architecture** pour le UseCase
4. **Implémenter** le code et les tests
5. **Valider** contre les tests d'acceptation
6. **Documenter** les changements

Pour contribuer :
1. Fork le repository
2. Créer une branche pour votre UseCase : `git checkout -b feature/uc-xyz`
3. Suivre le processus AGILE défini dans [IMPLEMENTATION_STRATEGY.md](./IMPLEMENTATION_STRATEGY.md)
4. Faire un Pull Request

## 📋 Checklist de Code

Avant chaque commit :
- [ ] Tous les tests unitaires passent
- [ ] Aucune exception non gérée
- [ ] Tests d'acceptation validés
- [ ] Pas de vulnérabilités OWASP
- [ ] Documentation mise à jour
- [ ] CHANGELOG complété avec date et heure
- [ ] Audit logging en place
- [ ] Performance acceptable

## 📞 Support

- **Issues** : Ouvrir une issue GitHub pour les bugs
- **Discussions** : Utiliser les discussions pour les questions
- **Security** : Rapporter les problèmes de sécurité privément

## 📄 Licence

Voir le fichier [LICENSE](./LICENSE) pour détails.

## 🗓️ Roadmap

```
Q4 2024 (Nov-Déc)
├── Phase 1 : Démarrage serveur
└── Phase 2 : Enregistrement tools

Q1 2025 (Jan-Mar)
├── Phase 3 : Authentification
├── Phase 4 : TCP/HTTP
└── Phase 5 : DBus

Q2 2025 (Avr-Jun)
├── Phase 6 : Sandbox
└── Phase 7 : Audit complet
```

---

**Dernière mise à jour :** 2025-11-23
**Version :** 0.1.0-alpha
**Statut :** En développement actif 🚀
