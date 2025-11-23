@echo off
REM Script d'installation pour Serveur MCP (Windows)
REM Crée un environnement virtuel Python isolé pour le projet

setlocal enabledelayedexpansion

REM Configuration
set PROJECT_NAME=mcp-server
set VENV_DIR=venv
set PYTHON_MIN_VERSION=3.10

REM Couleurs Windows (limité)
color 0A

echo.
echo ════════════════════════════════════════════════════════════
echo Installation du Serveur MCP
echo ════════════════════════════════════════════════════════════
echo.

REM 1. Vérifier Python
echo [*] Vérification de Python %PYTHON_MIN_VERSION%+
python --version >nul 2>&1
if errorlevel 1 (
    echo [X] Python3 n'est pas installé
    echo     Veuillez installer Python 3.10+ depuis https://www.python.org
    pause
    exit /b 1
)

for /f "tokens=2" %%i in ('python --version 2^>^&1') do (
    echo [+] Python %%i trouvé
)

REM 2. Vérifier Git
echo [*] Vérification de Git
git --version >nul 2>&1
if errorlevel 1 (
    echo [X] Git n'est pas installé
    echo     Veuillez installer Git depuis https://git-scm.com
    pause
    exit /b 1
)

for /f "tokens=3" %%i in ('git --version') do (
    echo [+] Git %%i trouvé
)

REM 3. Créer/Réinitialiser venv
echo.
echo [*] Configuration de l'environnement virtuel: %VENV_DIR%

if exist "%VENV_DIR%" (
    echo [!] Environnement virtuel existe déjà
    set /p REINIT="Réinitialiser ? (O/n): "
    if /i "!REINIT!"=="o" (
        echo [*] Suppression du venv existant...
        rmdir /s /q "%VENV_DIR%"
        call :create_venv
    )
) else (
    call :create_venv
)

REM 4. Activer venv
echo [*] Activation de l'environnement virtuel
call "%VENV_DIR%\Scripts\activate.bat"
if errorlevel 1 (
    echo [X] Impossible d'activer l'environnement virtuel
    pause
    exit /b 1
)
echo [+] Environnement virtuel activé

REM 5. Upgrader pip
echo [*] Mise à jour de pip
python -m pip install --upgrade pip -q
if errorlevel 1 (
    echo [X] Erreur lors de la mise à jour de pip
    pause
    exit /b 1
)
echo [+] pip mis à jour

REM 6. Installer les dépendances
echo [*] Installation des dépendances
if "%1"=="--prod" (
    echo [!] Mode production
    pip install -r requirements.txt
) else (
    echo [!] Mode développement (avec tests)
    pip install -r requirements-dev.txt
)
if errorlevel 1 (
    echo [X] Erreur lors de l'installation des dépendances
    pause
    exit /b 1
)
echo [+] Dépendances installées

REM 7. Vérifier l'installation
echo [*] Vérification de l'installation
python -c "import pydantic; print(f'[+] pydantic {pydantic.__version__}')" 2>nul
if errorlevel 1 (
    echo [X] Pydantic n'a pas pu être importé
    pause
    exit /b 1
)
echo [+] Installation vérifiée

REM 8. Afficher les commandes suivantes
echo.
echo ════════════════════════════════════════════════════════════
echo Installation Terminée !
echo ════════════════════════════════════════════════════════════
echo.
echo Environnement Python pret pour le developpement
echo.
echo Commandes disponibles:
echo   # Tester le client MCP
echo   python examples\example_client.py
echo.
echo   # Executer les tests
echo   python -m mcp_server.resources.execution_manager
echo   pytest mcp_server\ -v
echo.
echo   # Quitter l'environnement virtuel
echo   deactivate
echo.
echo Documentation:
echo   - INSTALL.md          pour details d'installation
echo   - examples\README.md   pour les exemples
echo   - ARCHITECTURE.md      pour l'architecture
echo.

if "%1"=="--prod" (
    echo [!] Mode production - Tests non installes
) else (
    echo Prochaines etapes:
    echo   1. Executer les tests: python examples\example_client.py
    echo   2. Consulter les exemples: examples\README.md
    echo   3. Lire la documentation: ARCHITECTURE.md
)
echo.
pause
exit /b 0

REM Fonction pour créer le venv
:create_venv
echo [*] Création du venv...
python -m venv "%VENV_DIR%"
if errorlevel 1 (
    echo [X] Impossible de créer l'environnement virtuel
    pause
    exit /b 1
)
echo [+] Environnement virtuel créé
exit /b 0
