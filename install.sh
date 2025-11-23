#!/bin/bash
# Script d'installation pour Serveur MCP (Linux/Mac)
# Crée un environnement virtuel Python isolé pour le projet

set -e  # Exit on error

# Couleurs pour l'output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_NAME="mcp-server"
VENV_DIR="venv"
PYTHON_MIN_VERSION="3.10"

# Functions
print_header() {
    echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_info() {
    echo -e "${YELLOW}ℹ $1${NC}"
}

print_step() {
    echo -e "\n${BLUE}→ $1${NC}"
}

# Main installation
main() {
    print_header "Installation du Serveur MCP"

    # 1. Vérifier Python
    print_step "Vérification de Python $PYTHON_MIN_VERSION+"

    if ! command -v python3 &> /dev/null; then
        print_error "Python3 n'est pas installé"
        echo "Veuillez installer Python 3.10+ depuis https://www.python.org"
        exit 1
    fi

    PYTHON_VERSION=$(python3 --version | awk '{print $2}')
    print_success "Python $PYTHON_VERSION trouvé"

    # 2. Vérifier Git
    print_step "Vérification de Git"
    if ! command -v git &> /dev/null; then
        print_error "Git n'est pas installé"
        exit 1
    fi
    print_success "Git $(git --version | awk '{print $3}') trouvé"

    # 3. Créer venv
    print_step "Création de l'environnement virtuel: $VENV_DIR"

    if [ -d "$VENV_DIR" ]; then
        print_info "Environnement virtuel existe déjà ($VENV_DIR)"
        read -p "Réinitialiser ? (y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            rm -rf "$VENV_DIR"
            python3 -m venv "$VENV_DIR"
            print_success "Environnement virtuel réinitialisé"
        fi
    else
        python3 -m venv "$VENV_DIR"
        print_success "Environnement virtuel créé"
    fi

    # 4. Activer venv
    print_step "Activation de l'environnement virtuel"
    source "$VENV_DIR/bin/activate"
    print_success "Environnement virtuel activé"

    # 5. Upgrader pip
    print_step "Mise à jour de pip"
    python -m pip install --upgrade pip --quiet
    print_success "pip mis à jour"

    # 6. Installer les dépendances
    print_step "Installation des dépendances"

    # Mode développement par défaut
    if [ "$1" == "--prod" ]; then
        print_info "Mode production"
        pip install -r requirements.txt
    else
        print_info "Mode développement (avec tests)"
        pip install -r requirements-dev.txt
    fi

    print_success "Dépendances installées"

    # 7. Vérifier l'installation
    print_step "Vérification de l'installation"

    python -c "import pydantic; print(f'✓ pydantic {pydantic.__version__}')" 2>/dev/null || {
        print_error "Pydantic n'a pas pu être importé"
        exit 1
    }

    print_success "Installation vérifiée"

    # 8. Afficher les commandes suivantes
    echo ""
    print_header "Installation Terminée ✓"
    echo ""
    echo -e "${GREEN}Environnement Python prêt pour le développement${NC}"
    echo ""
    echo -e "${YELLOW}Commandes disponibles:${NC}"
    echo "  # Tester le client MCP"
    echo "  python examples/example_client.py"
    echo ""
    echo "  # Exécuter les tests"
    echo "  python -m mcp_server.resources.execution_manager"
    echo "  python -m pytest mcp_server/ -v"
    echo ""
    echo "  # Quitter l'environnement virtuel"
    echo "  deactivate"
    echo ""
    echo -e "${YELLOW}Documentation:${NC}"
    echo "  - INSTALL.md          pour détails d'installation"
    echo "  - examples/README.md   pour les exemples"
    echo "  - ARCHITECTURE.md      pour l'architecture"
    echo ""

    if [ "$1" == "--prod" ]; then
        print_info "Mode production - Tests non installés"
    else
        echo -e "${BLUE}Prochaines étapes:${NC}"
        echo "  1. Exécuter les tests: python examples/example_client.py"
        echo "  2. Consulter les exemples: examples/README.md"
        echo "  3. Lire la documentation: ARCHITECTURE.md"
    fi
    echo ""
}

# Handle errors
trap 'print_error "Installation échouée"; exit 1' ERR

# Run main
main "$@"
