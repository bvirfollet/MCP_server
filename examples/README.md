# Exemples de Client MCP - Phase 2

Ce répertoire contient des clients MCP d'exemple pour démontrer les capacités du serveur MCP.

## 📋 Contenu

### `example_client.py` - Démonstration Phase 2

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

## 🚀 Utilisation

### Exécuter la démonstration:

```bash
# Depuis la racine du projet
python examples/example_client.py
```

### Output de démonstration:

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

- Voir [`../mcp_server/tools/tool.py`](../mcp_server/tools/tool.py) pour la classe Tool
- Voir [`../mcp_server/security/permission.py`](../mcp_server/security/permission.py) pour les permissions
- Voir [`../mcp_server/resources/execution_manager.py`](../mcp_server/resources/execution_manager.py) pour l'exécution sécurisée
