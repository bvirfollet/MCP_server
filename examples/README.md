# Exemples de Client MCP - Phase 1, 2, et 3

Ce répertoire contient des clients MCP d'exemple pour démontrer les capacités du serveur MCP à travers les 3 phases de développement.

## 📋 Contenu

### `example_client.py` - Démonstration Phase 1-2 (RBAC & Permissions)

Client de démonstration complet montrant:

1. **Enregistrement d'outils** avec le décorateur `@server.tool()`
   - Outil simple sans permission: `greet`
   - Outil avec permission FILE_READ: `read_status`
   - Outil avec permission CODE_EXECUTION: `execute_code`

2. **Système RBAC (Permissions)**
   - Listing des outils avec permissions requises
   - Gestion des permissions par client
   - Vérification avant exécution

3. **Exécution sécurisée**
   - Validation des paramètres
   - Isolation par sandbox client
   - Timeouts d'exécution

4. **Audit trail complet**
   - Logging de chaque exécution
   - Statut de succès/erreur
   - Durée d'exécution

5. **Statistiques**
   - Taux de succès
   - Durée moyenne d'exécution
   - État du sandbox client

### `example_heatmodel_client.py` - Démonstration Phase 1, 2, et 3 (HeatSimulation Integration)

Client réaliste pour la construction de modèles volumétriques 3D de maisons, démontrant l'intégration complète avec le projet [HeatSimulation](https://github.com/bvirfollet/HeatSimulation).

**Phases démontrées:**

1. **Phase 1: Transport Stdio**
   - Communication JSON-RPC asynchrone avec le serveur MCP
   - Requêtes et réponses structurées

2. **Phase 2: Outils et Permissions**
   - 5 outils d'exemple pour la modélisation 3D:
     - `initialize_model` - Création d'une grille 3D
     - `add_volume` - Ajout de volumes rectangulaires avec matériaux
     - `list_materials` - Affichage des matériaux disponibles (10+ types)
     - `get_model_info` - Statistiques du modèle
     - `export_to_json` - Export JSON (requiert permission FILE_WRITE)
   - Système RBAC avec vérification des permissions avant exécution

3. **Phase 3: Authentification JWT et Audit**
   - Création de client avec authentification bcrypt
   - Génération de tokens JWT (access + refresh)
   - Audit trail immutable avec 15+ événements loggés
   - Persistance JSON (clients.json, tokens.json, audit.json)

**Modèle construit:**

Le client construit une **maison passive réaliste** compatible avec HeatSimulation:

- **Dimensions**: 12m (X) × 10m (Y) × 5m (Z)
- **Résolution**: Grille 0.2m (60 × 50 × 25 = 75,000 voxels)
- **Couches** (de bas en haut):
  - Terre (TERRE) - Couplage thermique sol
  - Fondation (BETON) - Masse thermique
  - Isolation sol (POLYSTYRENE) - R-value élevée
  - Zone intérieure (AIR) - Espace climatisé 11.4m × 9.4m × 2.65m
  - Murs composites (MUR_COMPOSITE_EXT) - Isolation intégrée
  - Isolation comble (LAINE_BOIS) - Faible conductivité
  - Toiture (BETON) - Élément structurel

**Export compatible HeatSimulation:**

```json
{
  "metadata": {"version": "1.0", "description": "Modèle volumétrique 3D"},
  "geometry": {"dimensions": {...}, "grid_size": {...}},
  "volumes": [...],
  "materials": {...},
  "statistics": {...}
}
```

Pour la documentation complète, voir [HEATMODEL_CLIENT_GUIDE.md](./HEATMODEL_CLIENT_GUIDE.md).

## 🚀 Utilisation

### Exécuter les démonstrations:

#### Client RBAC & Permissions (Phase 1-2):
```bash
cd /mnt/share/Sources/MCP_server
python examples/example_client.py
```

#### Client HeatSimulation (Phase 1-2-3):
```bash
cd /mnt/share/Sources/MCP_server
mkdir -p data_heatmodel  # Créer le répertoire de sortie
python examples/example_heatmodel_client.py
```

### Output de démonstration (example_client.py):

Le client va :
1. **Créer un serveur** avec 3 outils d'exemple
2. **Lister les outils** disponibles avec leurs permissions
3. **Exécuter les outils** dans différents scénarios:
   - ✓ Exécution réussie (sans permission)
   - ✗ Permission refusée (sans autorisation)
   - ✓ Exécution réussie (après grant de permission)
4. **Afficher l'audit trail** complet
5. **Afficher les statistiques** de session

### Résultats attendus:

```
======================================================================
🎯 DÉMONSTRATION CLIENT MCP - PHASE 2
======================================================================

✓ Serveur configuré avec 3 outils d'exemple

======================================================================
📋 LISTING DES OUTILS (tools/list)
======================================================================

🔧 greet
   Description: Salue un utilisateur par son nom
   Permissions: Aucune

🔧 read_status
   Description: Lit le statut d'un fichier
   Permissions requises: FILE_READ:/tmp/*

🔧 execute_code
   Description: Exécute du code Python (restreint)
   Permissions requises: CODE_EXECUTION:restricted

======================================================================
🔐 DÉMONSTRATION DES PERMISSIONS
======================================================================

[1] Appel de 'greet' (pas de permission requise)
✓ Succès!

[2] Appel de 'read_status' (FILE_READ non autorisé - devrait échouer)
❌ Erreur lors de l'exécution: PermissionDeniedError

[3] Accordage de permission FILE_READ au client
✓ Permission accordée

[4] Nouvel appel de 'read_status' (devrait réussir)
✓ Succès!

======================================================================
📊 STATISTIQUES
======================================================================
Exécutions totales: 4
Succès: 2
Erreurs: 2
Taux de succès: 50.0%

✓ DÉMONSTRATION TERMINÉE AVEC SUCCÈS
```

## 📚 Architecture démontrée

```
┌──────────────────────────────────┐
│   Client MCP (example_client)     │
└────────────┬─────────────────────┘
             │
             ├─→ tools/list    (Listing des outils)
             └─→ tools/call    (Exécution des outils)
                     │
                     ▼
        ┌────────────────────────┐
        │  ToolManager           │
        │  (Registre d'outils)   │
        └────────────┬───────────┘
                     │
                     ▼
        ┌────────────────────────┐
        │  PermissionManager      │
        │  (Vérification RBAC)    │
        └────────────┬───────────┘
                     │
                     ▼
        ┌────────────────────────┐
        │  ExecutionManager       │
        │  + SandboxContext       │
        │  (Exécution sécurisée)  │
        └────────────────────────┘
```

## 🔐 Sécurité démontrée

1. **Isolation par client** - Chaque client a son propre SandboxContext
2. **RBAC (Role-Based Access Control)** - Les permissions contrôlent l'accès
3. **Audit trail** - Tous les appels sont loggés avec statut et durée
4. **Validation des paramètres** - Les paramètres sont validés contre le schéma
5. **Timeouts** - Les outils s'exécutent avec timeout (30s par défaut)

## 📝 Notes

- Ce client crée son propre serveur en mémoire
- Les outils d'exemple sont très simplifiés pour la démonstration
- En production, vous vous connecteriez à un serveur distant
- Les permissions sont accordées/révoquées dynamiquement

## 🔗 Références

### Documentation des Clients
- **[HEATMODEL_CLIENT_GUIDE.md](./HEATMODEL_CLIENT_GUIDE.md)** - Guide complet du client HeatSimulation (Phase 3 integration test)

### Composants MCP (Phase 1-2)
- [`../mcp_server/tools/tool.py`](../mcp_server/tools/tool.py) - Classe Tool abstraite
- [`../mcp_server/security/permission.py`](../mcp_server/security/permission.py) - Système RBAC (Permissions)
- [`../mcp_server/resources/execution_manager.py`](../mcp_server/resources/execution_manager.py) - Exécution sécurisée

### Composants Authentification (Phase 3)
- [`../mcp_server/security/authentication/jwt_handler.py`](../mcp_server/security/authentication/jwt_handler.py) - JWT generation/validation
- [`../mcp_server/security/authentication/client_manager.py`](../mcp_server/security/authentication/client_manager.py) - Client credentials avec bcrypt
- [`../mcp_server/persistence/token_store.py`](../mcp_server/persistence/token_store.py) - Persistance tokens.json
- [`../mcp_server/persistence/audit_store.py`](../mcp_server/persistence/audit_store.py) - Audit trail immutable

### Architecture Générale
- [`../ARCHITECTURE.md`](../ARCHITECTURE.md) - Architecture générale du serveur MCP
- [`../ARCHITECTURE_PHASE3.md`](../ARCHITECTURE_PHASE3.md) - Architecture Phase 3 (Authentification & Persistance)
