# Guide d'Installation - Serveur MCP

## 📋 Prérequis

- **Python 3.10+** (recommandé 3.11 ou 3.12)
- **Git** (pour cloner le repository)
- **pip** (gestionnaire de paquets Python)
- **venv** (ou virtualenv, pour l'isolation)

## 🚀 Installation Rapide

### 1. Cloner le repository

```bash
git clone https://github.com/yourusername/mcp-server.git
cd mcp-server
```

### 2. Créer un environnement virtuel

```bash
# Linux/Mac
python3 -m venv venv
source venv/bin/activate

# Windows
python -m venv venv
venv\Scripts\activate
```

### 3. Installer les dépendances

#### Mode développement (avec tests)
```bash
pip install -r requirements-dev.txt
```

#### Mode production uniquement
```bash
pip install -r requirements.txt
```

### 4. Vérifier l'installation

```bash
# Vérifier la version Python
python --version

# Vérifier les dépendances installées
pip list
```

## 🧪 Exécuter les Tests

### Tous les tests

```bash
# Tests Phase 1 et Phase 2 (149 tests)
python -m mcp_server.security.permission
python -m mcp_server.tools.tool
python -m mcp_server.tools.tool_manager
python -m mcp_server.security.permission_manager
python -m mcp_server.resources.sandbox_context
python -m mcp_server.resources.execution_manager
python -m mcp_server.core.mcp_server
```

### Tests spécifiques

```bash
# Tests Phase 1 uniquement
python -m mcp_server.core.constants
python -m mcp_server.transport.base_transport
python -m mcp_server.transport.stdio_transport
python -m mcp_server.protocol.mcp_protocol_handler
python -m mcp_server.security.client_context

# Tests Phase 2 uniquement
python -m mcp_server.security.permission
python -m mcp_server.tools.tool
python -m mcp_server.tools.tool_manager
python -m mcp_server.security.permission_manager
python -m mcp_server.resources.sandbox_context
python -m mcp_server.resources.execution_manager
```

### Avec pytest (si installé)

```bash
# Tous les tests
pytest mcp_server/ -v

# Tests d'un module spécifique
pytest mcp_server/security/permission.py -v

# Avec couverture de code
pytest mcp_server/ --cov=mcp_server --cov-report=html
```

## 📚 Exemples d'Utilisation

### Client MCP de Démonstration

```bash
# Phase 2 - Démonstration complète des permissions et exécution
python examples/example_client.py
```

Cet exemple montre:
- Enregistrement d'outils avec le décorateur `@server.tool()`
- Système RBAC avec 3 outils (permissions variées)
- Listing des outils (tools/list)
- Exécution sécurisée (tools/call)
- Audit trail et statistiques

### Résultats attendus

```
======================================================================
🎯 DÉMONSTRATION CLIENT MCP - PHASE 2
======================================================================

✓ Serveur configuré avec 3 outils d'exemple
  1. greet - Salutation (aucune permission)
  2. read_status - Lecture fichier (FILE_READ)
  3. execute_code - Exécution code (CODE_EXECUTION)

======================================================================
📋 LISTING DES OUTILS (tools/list)
======================================================================

🔧 greet
   Description: Salue un utilisateur par son nom
   Permissions: Aucune

[... résultats des permissions et exécutions ...]

======================================================================
📊 STATISTIQUES
======================================================================
Exécutions totales: 4
Succès: 2
Erreurs: 2
Taux de succès: 50.0%

✓ DÉMONSTRATION TERMINÉE AVEC SUCCÈS
```

## 🏗️ Structure de l'Installation

```
mcp-server/
├── pyproject.toml              # Configuration du projet
├── requirements.txt            # Dépendances production
├── requirements-dev.txt        # Dépendances développement
├── INSTALL.md                  # Ce fichier
│
├── mcp_server/
│   ├── core/
│   │   ├── constants.py       # Constantes globales
│   │   └── mcp_server.py      # Serveur principal
│   ├── transport/
│   │   ├── base_transport.py
│   │   └── stdio_transport.py
│   ├── protocol/
│   │   └── mcp_protocol_handler.py
│   ├── security/
│   │   ├── client_context.py
│   │   ├── permission.py      # RBAC system
│   │   └── permission_manager.py
│   ├── tools/
│   │   ├── tool.py           # Abstract tool class
│   │   └── tool_manager.py    # Tool registry
│   └── resources/
│       ├── sandbox_context.py # Client isolation
│       └── execution_manager.py # Secure execution
│
└── examples/
    ├── example_client.py      # Client de démo
    └── README.md              # Guide des exemples
```

## 🐛 Dépannage

### Python 3.10+ n'est pas trouvé

```bash
# Sur Mac avec Homebrew
brew install python@3.12

# Sur Ubuntu/Debian
sudo apt-get install python3.12 python3.12-venv

# Sur Windows, téléchargez depuis https://www.python.org
```

### Erreur de dépendances

```bash
# Mettre à jour pip
pip install --upgrade pip

# Réinstaller les dépendances
pip install -r requirements-dev.txt --force-reinstall
```

### Erreur "Module not found"

```bash
# Ajouter le répertoire courant au PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

# Ou installer le package en mode développement
pip install -e .
```

### Les tests ne s'exécutent pas

```bash
# Vérifier que vous êtes dans l'environnement virtuel
source venv/bin/activate  # Linux/Mac
# ou
venv\Scripts\activate     # Windows

# Vérifier Python
python --version
```

## 📊 Statistiques de Test

Après installation et tests réussis:

```
Phase 1 Tests:
  ✅ 73 tests passants
  - Transport (Stdio)
  - Protocol (MCP)
  - Security (Client Context)
  - Core (Constants, MCPServer)

Phase 2 Tests:
  ✅ 76 tests passants
  - Security (Permission, PermissionManager)
  - Tools (Tool, ToolManager)
  - Resources (SandboxContext, ExecutionManager)

─────────────────
TOTAL: 149 tests ✅
```

## 🔐 Vérification de Sécurité

Après installation, vous pouvez vérifier:

```python
from mcp_server.security.permission import Permission, PermissionType

# Créer une permission
perm = Permission(PermissionType.FILE_READ, "/app/data/*")

# Vérifier les wildcard patterns
assert perm.matches(Permission(PermissionType.FILE_READ, "/app/data/file.txt"))
assert not perm.matches(Permission(PermissionType.FILE_READ, "/etc/passwd"))

print("✓ Système de permissions validé")
```

## 📖 Documentation Complète

- **[README.md](./README.md)** - Vue d'ensemble du projet
- **[ARCHITECTURE.md](./ARCHITECTURE.md)** - Architecture générale
- **[SECURITY.md](./SECURITY.md)** - Politique de sécurité
- **[CHANGELOG.md](./CHANGELOG.md)** - Historique des changements
- **[examples/README.md](./examples/README.md)** - Guide des exemples

## 🤝 Contribution

Pour contribuer au projet:

1. Fork le repository
2. Créer une branche feature (`git checkout -b feature/AmazingFeature`)
3. Commit les changes (`git commit -m 'Add AmazingFeature'`)
4. Push vers la branche (`git push origin feature/AmazingFeature`)
5. Ouvrir une Pull Request

## 📝 Licence

Ce projet est licencié sous la Licence MIT - voir le fichier [LICENSE](./LICENSE) pour plus de détails.

## 📞 Support

Pour toute question ou problème:
- Consultez la [FAQ](./docs/FAQ.md) (à venir)
- Ouvrez une [issue GitHub](https://github.com/yourusername/mcp-server/issues)
- Consultez la documentation complète

---

**Dernière mise à jour:** 2025-11-23
**Version:** 0.2.0-alpha
