# UseCase 2 : Tools & Permissions Management

**Phase** : Phase 2
**Date** : 2025-11-23
**Status** : En Planification

---

## 1. Description du UseCase

### Objectif Principal
Permettre aux clients MCP de :
1. **Enregistrer des tools** (ressources/fonctions exécutables)
2. **Déclarer les permissions requises** pour chaque tool
3. **Exécuter les tools** dans un contexte sécurisé
4. **Valider les permissions** avant exécution

### Acteurs
- **Client MCP** (IA : Claude, GPT, Gemini)
- **Serveur MCP** (orchestrateur)
- **Module Enregistreur** (déclare les tools)
- **Permission Manager** (vérifie les droits)
- **Execution Manager** (exécute avec isolation)

### Flux Principal

```
1. Module registre ses tools (au démarrage)
   │
   ├─→ Tool 1: read_file
   │    Permission: FILE_READ
   │    Paramètres: path (string), encoding (string)
   │
   ├─→ Tool 2: write_file
   │    Permission: FILE_WRITE
   │    Paramètres: path (string), content (string)
   │
   └─→ Tool 3: execute_code
        Permission: CODE_EXECUTION
        Paramètres: code (string), timeout (int)

2. Client IA demande la liste des tools
   │
   └─→ Serveur répond avec:
       - Nom du tool
       - Description
       - Schéma des paramètres
       - Permissions requises

3. Client appelle un tool
   │
   ├─→ Validation des paramètres
   ├─→ Vérification des permissions
   ├─→ Exécution du tool
   └─→ Retour du résultat

4. Tool s'exécute
   │
   ├─→ Dans le contexte client (sandbox)
   ├─→ Avec les permissions accordées
   ├─→ Avec timeout et limites de ressources
   └─→ Audit logging de l'opération
```

---

## 2. Tests d'Acceptation (Gherkin)

### Feature 1: Enregistrement de Tools

```gherkin
Feature: Enregistrement de Tools
  Un module doit pouvoir enregistrer ses tools auprès du serveur MCP

  Scenario: Enregistrement simple d'un tool
  Given: Le serveur MCP est en cours d'exécution
  When: Un module enregistre un tool "read_file"
       Et le tool déclare la permission FILE_READ
  Then: Le serveur doit accepter l'enregistrement
       Et le tool doit être disponible pour les clients

  Scenario: Enregistrement avec validation de schéma
  Given: Le serveur MCP est en cours d'exécution
  When: Un module enregistre un tool avec un schéma JSON invalide
  Then: Le serveur doit rejeter l'enregistrement
       Et retourner une erreur descriptive

  Scenario: Enregistrement de tool avec permissions multiples
  Given: Le serveur MCP est en cours d'exécution
  When: Un module enregistre un tool requérant:
        - FILE_READ sur /app/data/*
        - FILE_WRITE sur /app/output/*
        - SYSTEM_COMMAND (ls, grep uniquement)
  Then: Le serveur doit accepter et mémoriser toutes les permissions

  Scenario: Erreur - doublon de tool
  Given: Un tool "read_file" est déjà enregistré
  When: Un autre module tente d'enregistrer un tool "read_file"
  Then: Le serveur doit rejeter avec erreur "Tool already exists"
```

### Feature 2: Exposition des Tools

```gherkin
Feature: Exposition des Tools
  Les clients doivent pouvoir découvrir les tools disponibles

  Scenario: Lister tous les tools disponibles
  Given: Le serveur MCP a 3 tools enregistrés
  When: Un client appelle "tools/list"
  Then: Le serveur retourne une liste avec:
        - Nom du tool
        - Description complète
        - Schéma des paramètres d'entrée
        - Schéma du résultat
        - Permissions requises

  Scenario: Détails d'un tool spécifique
  Given: Un tool "read_file" est enregistré
  When: Un client demande les détails du tool
  Then: Le serveur retourne:
        - Input schema: {path: string, encoding: string}
        - Output schema: {content: string, size: int}
        - Permissions: [FILE_READ]
        - Description: "Lire un fichier"

  Scenario: Format de réponse conforme MCP
  Given: Client demande la liste des tools
  When: Serveur retourne la réponse
  Then: La réponse doit être au format:
        {
          "tools": [
            {
              "name": "string",
              "description": "string",
              "inputSchema": {...},
              "permissions": [...]
            }
          ]
        }
```

### Feature 3: Système de Permissions

```gherkin
Feature: Système de Permissions (RBAC)
  Vérifier et appliquer les permissions avant exécution

  Scenario: Client avec permission - exécution acceptée
  Given: Client "ai_assistant_1" a permission FILE_READ
       Et tool "read_file" requiert FILE_READ
  When: Client appelle le tool avec paramètres valides
  Then: Le tool doit s'exécuter
       Et retourner le résultat

  Scenario: Client sans permission - exécution refusée
  Given: Client "ai_assistant_1" n'a PAS permission FILE_WRITE
       Et tool "write_file" requiert FILE_WRITE
  When: Client appelle le tool
  Then: Serveur doit retourner erreur:
        {
          "code": -32102,
          "message": "Permission denied: FILE_WRITE"
        }

  Scenario: Permission avec chemin limité
  Given: Client a permission FILE_READ sur /app/data/*.txt seulement
  When: Client appelle read_file("/app/data/config.json")
  Then: L'appel doit échouer avec "Path out of scope"

  When: Client appelle read_file("/app/data/file.txt")
  Then: L'appel doit réussir

  Scenario: Permission de code execution réstreinte
  Given: Client a CODE_EXECUTION avec restricted=true
  When: Client tente d'exécuter:
        import os; os.system("rm -rf /")
  Then: L'exécution doit être bloquée
       Et erreur retournée

  Scenario: Permission de commande système avec whitelist
  Given: Client a SYSTEM_COMMAND avec whitelist: ["ls", "grep"]
  When: Client tente d'exécuter "cat /etc/passwd"
  Then: L'exécution doit échouer

  When: Client exécute "ls /app/data"
  Then: L'exécution doit réussir
```

### Feature 4: Exécution de Tools

```gherkin
Feature: Exécution Sécurisée de Tools
  Exécuter les tools avec isolation et contrôle de ressources

  Scenario: Exécution simple avec résultat
  Given: Client appelle tool avec paramètres valides
  When: Tool s'exécute sans erreur
  Then: Serveur retourne:
        {
          "result": { ... },
          "executionTime": 45,
          "success": true
        }

  Scenario: Timeout d'exécution
  Given: Tool a timeout configuré à 30 secondes
  When: Tool s'exécute plus longtemps que timeout
  Then: Exécution doit être stoppée
       Et erreur retournée:
        {
          "code": -32105,
          "message": "Execution timeout"
        }

  Scenario: Erreur d'exécution gérée
  Given: Tool lève une exception
  When: Tool s'exécute
  Then: Erreur doit être capturée et retournée:
        {
          "code": -32105,
          "message": "Execution error: ...",
          "data": {"error_type": "...", "traceback": "..."}
        }

  Scenario: Isolation du contexte client
  Given: Client 1 et Client 2 appellent des tools
  When: Les deux exécutent en parallèle
  Then: Variables/state ne doivent pas se mélanger
       Et chaque client doit avoir son contexte isolé

  Scenario: Limitation de ressources
  Given: Client appelle tool gourmand en mémoire
  When: Allocation mémoire dépasse la limite
  Then: Exécution doit être arrêtée
       Et erreur retournée
```

### Feature 5: Audit & Logging

```gherkin
Feature: Audit et Logging
  Tracer toutes les opérations sur les tools

  Scenario: Log d'appel de tool réussi
  Given: Client appelle un tool avec succès
  When: Tool s'exécute
  Then: Un log doit être créé:
        {
          "timestamp": "2025-11-23T15:30:45Z",
          "event_type": "tool_called",
          "client_id": "ai_assistant_1",
          "tool_name": "read_file",
          "status": "success",
          "execution_time_ms": 45
        }

  Scenario: Log de tentative d'accès refusée
  Given: Client essaie d'exécuter sans permission
  When: Permission denied
  Then: Un log doit être créé:
        {
          "event_type": "permission_denied",
          "client_id": "...",
          "tool_name": "...",
          "required_permission": "...",
          "severity": "WARNING"
        }

  Scenario: Log d'erreur d'exécution
  Given: Tool lève une exception
  When: Tool s'exécute
  Then: Un log doit être créé:
        {
          "event_type": "tool_error",
          "client_id": "...",
          "tool_name": "...",
          "error_message": "...",
          "severity": "ERROR"
        }
```

---

## 3. Critères de Succès Phase 2

### Fonctionnels
- ✅ Enregistrement de tools avec validation
- ✅ Exposition de tools via tools/list
- ✅ Vérification des permissions avant exécution
- ✅ Exécution sécurisée de tools
- ✅ Gestion des timeouts
- ✅ Audit logging complète

### Non-Fonctionnels
- ✅ Tous les tests unitaires passent (50+ nouveau)
- ✅ Tests d'acceptation passent
- ✅ Pas de dégradation de performance
- ✅ Pas de fuite mémoire
- ✅ Documentation complète

### Sécurité
- ✅ Pas de code injection possible
- ✅ Permissions strictement vérifiées
- ✅ Isolation du contexte client
- ✅ Pas de permission escalation
- ✅ Audit trail complet

---

## 4. Dépendances Phase 2

### Dépend de Phase 1
- ✅ MCPServer
- ✅ MCPProtocolHandler
- ✅ ClientContext
- ✅ StdioTransport

### Composants à Créer

| Composant | Responsabilité |
|-----------|-----------------|
| **ToolManager** | Enregistrement et exposition des tools |
| **PermissionManager** | Vérification des permissions (RBAC) |
| **ExecutionManager** | Exécution sécurisée des tools |
| **Tool** (classe de base) | Interface pour déclarer les tools |
| **Permission** (dataclass) | Représentation des permissions |
| **ToolRegistry** | Registre central des tools |

---

## 5. Questions de Clarification (À Poser)

Avant de continuer, j'aurais besoin de clarifier :

### Q1 : Modèle d'Enregistrement des Tools

**Question** : Comment souhaitez-vous que les modules enregistrent leurs tools ?

**Options** :
- [ ] A) Décorateur Python (`@server.tool()`)
- [ ] B) Classe qui hérite de `BaseTool`
- [ ] C) Fonction de registration explicite (`server.register_tool()`)
- [ ] D) Configuration externe (fichier YAML/JSON)

### Q2 : Isolation d'Exécution

**Question** : Quel niveau d'isolation pour l'exécution des tools ?

**Options** :
- [ ] A) Namespace Python sécurisé (pas d'imports système)
- [ ] B) Processus séparé pour chaque exécution
- [ ] C) Container Docker par client
- [ ] D) Combinaison A + B (Python pour Phase 2, processus pour Phase 6)

### Q3 : Permissions par Défaut

**Question** : Quelle stratégie pour les clients sans permissions explicites ?

**Options** :
- [ ] A) Refus total (deny-all par défaut)
- [ ] B) Permissions minimales (read-only)
- [ ] C) Permissions spécifiées explicitement pour chaque client

### Q4 : Exécution de Code

**Question** : Pour le tool CODE_EXECUTION, comment gérer le code utilisateur ?

**Options** :
- [ ] A) eval/exec dans namespace sécurisé (restriction d'imports)
- [ ] B) AST parsing + whitelist de fonctions permises
- [ ] C) Compilation bytecode + vérification statique
- [ ] D) Pas d'exécution de code libre (seulement tools pré-enregistrés)

### Q5 : Sandbox Client

**Question** : Chaque client doit-il avoir son propre répertoire de travail ?

**Options** :
- [ ] A) Oui, répertoire isolé par client
- [ ] B) Répertoire partagé avec restrictions d'accès
- [ ] C) Pas de répertoire (tools sans état)

---

## 6. Plan d'Implémentation (Basique)

### Étape 1 : Foundations (4h)
- Créer classes de base (`Tool`, `Permission`)
- Créer `ToolRegistry` (registre central)
- Intégrer dans `MCPServer`

### Étape 2 : Tool Manager (6h)
- Enregistrement de tools
- Exposition via `tools/list`
- Validation des schémas

### Étape 3 : Permission Manager (6h)
- Vérification des permissions
- Gestion des permissions par client
- Audit logging

### Étape 4 : Execution Manager (8h)
- Exécution sécurisée
- Gestion des timeouts
- Gestion des erreurs

### Étape 5 : Tests (6h)
- Tests unitaires (50+)
- Tests d'intégration (20+)
- Tests de sécurité

### Total Estimé : **30 heures**

---

**Prêt pour continuer ?**

Je vais attendre votre réponse aux questions de clarification avant de poursuivre avec l'architecture détaillée.

