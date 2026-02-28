#!/usr/bin/env bash
set -euo pipefail

# ──────────────────────────────────────────────────────────────
# Post-install setup script for Arch Linux & macOS
# Detects the OS and uses the appropriate package manager
#   Linux: yay (AUR helper)
#   macOS: Homebrew
# Stows the correct dotfiles per platform, then restores
# the git version via checkout after adopt.
# ──────────────────────────────────────────────────────────────

DOTFILES_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OS="$(uname -s)"
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }
section() { echo -e "\n${BLUE}── $* ──${NC}"; }

# ══════════════════════════════════════════════════════════════
#  Package Manager Setup
# ══════════════════════════════════════════════════════════════

install_yay() {
    if command -v yay &>/dev/null; then
        info "yay is already installed"
        return
    fi
    info "Installing yay..."
    sudo pacman -S --needed --noconfirm base-devel git
    tmpdir=$(mktemp -d)
    git clone https://aur.archlinux.org/yay.git "$tmpdir/yay"
    (cd "$tmpdir/yay" && makepkg -si --noconfirm)
    rm -rf "$tmpdir"
    info "yay installed successfully"
}

install_homebrew() {
    if command -v brew &>/dev/null; then
        info "Homebrew is already installed"
        return
    fi
    info "Installing Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    # Add brew to PATH for the rest of this script
    eval "$(/opt/homebrew/bin/brew shellenv)"
    info "Homebrew installed successfully"
}

# ══════════════════════════════════════════════════════════════
#  Package Installation
# ══════════════════════════════════════════════════════════════

install_packages_linux() {
    local packages=(
        # Shell & terminal
        zsh
        kitty
        fzf
        zoxide
        eza
        yazi
        starship
        stow

        # Browsers
        google-chrome
        zen-browser-bin

        # Apps
        slack-desktop

        # Dev
        neovim
        git
        git-lfs
    )

    info "Installing packages via yay..."
    yay -S --needed --noconfirm "${packages[@]}"
    info "Packages installed"
}

install_packages_mac() {
    local formulae=(
        # Shell & terminal
        zsh
        fzf
        zoxide
        eza
        yazi
        starship
        stow
        autojump
        nvm
        neovim
        git
        git-lfs
    )

    local casks=(
        kitty
        alacritty
        ghostty
        google-chrome
        zen-browser
        slack
        nikitabobko/tap/aerospace
    )

    info "Installing formulae via Homebrew..."
    brew install "${formulae[@]}" || true

    info "Installing casks via Homebrew..."
    for cask in "${casks[@]}"; do
        brew install --cask "$cask" 2>/dev/null || brew install "$cask" 2>/dev/null || warn "Could not install $cask, skipping"
    done

    info "Packages installed"
}

# ══════════════════════════════════════════════════════════════
#  Shell Dependencies (cross-platform)
# ══════════════════════════════════════════════════════════════

install_shell_deps() {
    # fzf-tab
    local fzf_tab_dir="$HOME/Documents/fzf-tab"
    if [[ -d "$fzf_tab_dir" ]]; then
        info "fzf-tab already cloned"
    else
        info "Cloning fzf-tab..."
        mkdir -p "$HOME/Documents"
        git clone https://github.com/Aloxaf/fzf-tab "$fzf_tab_dir"
        info "fzf-tab installed to $fzf_tab_dir"
    fi

    # atuin
    if command -v atuin &>/dev/null || [[ -f "$HOME/.atuin/bin/atuin" ]]; then
        info "atuin is already installed"
    else
        info "Installing atuin..."
        curl -sSf https://setup.atuin.sh | bash
        info "atuin installed"
    fi
}

# ══════════════════════════════════════════════════════════════
#  Default Shell
# ══════════════════════════════════════════════════════════════

set_default_shell() {
    if [[ "$SHELL" == *"zsh"* ]]; then
        info "zsh is already the default shell"
        return
    fi
    info "Setting zsh as default shell..."
    chsh -s "$(which zsh)"
    info "Default shell set to zsh (takes effect on next login)"
}

# ══════════════════════════════════════════════════════════════
#  Verify Dependencies for Stow Packages
# ══════════════════════════════════════════════════════════════

# Maps a stow package name to the command it requires.
# Packages not listed here have no binary dependency (e.g. themes, bin).
pkg_to_cmd() {
    case "$1" in
        kitty)       echo "kitty" ;;
        alacritty)   echo "alacritty" ;;
        ghostty)     echo "ghostty" ;;
        git)         echo "git" ;;
        nvim)        echo "nvim" ;;
        starship)    echo "starship" ;;
        eza)         echo "eza" ;;
        yazi)        echo "yazi" ;;
        zsh|zsh-mac) echo "zsh" ;;
        hypr)        echo "Hyprland" ;;
        waybar)      echo "waybar" ;;
        aerospace)   echo "aerospace" ;;
        sketchybar)  echo "sketchybar" ;;
        *)           echo "" ;;  # no dependency to check
    esac
}

verify_stow_deps() {
    local packages=("$@")
    local missing=()

    for pkg in "${packages[@]}"; do
        local cmd
        cmd=$(pkg_to_cmd "$pkg")
        if [[ -n "$cmd" ]] && ! command -v "$cmd" &>/dev/null; then
            missing+=("$pkg -> $cmd")
        fi
    done

    if [[ ${#missing[@]} -gt 0 ]]; then
        warn "The following stow packages have missing dependencies:"
        for m in "${missing[@]}"; do
            warn "  $m"
        done
        echo ""
        read -rp "Continue stowing anyway? [y/N] " answer
        if [[ ! "$answer" =~ ^[Yy]$ ]]; then
            error "Aborting. Install missing dependencies and re-run."
        fi
    else
        info "All stow package dependencies verified"
    fi
}

# ══════════════════════════════════════════════════════════════
#  Stow Dotfiles
# ══════════════════════════════════════════════════════════════

stow_dotfiles() {
    local stow_packages=()

    # Shared packages (both platforms)
    local shared_packages=(
        kitty
        alacritty
        ghostty
        git
        nvim
        starship
        eza
        yazi
        bash
        bin
    )

    if [[ "$OS" == "Linux" ]]; then
        stow_packages=(
            "${shared_packages[@]}"
            zsh
            hypr
            waybar
            themes
        )
    elif [[ "$OS" == "Darwin" ]]; then
        stow_packages=(
            "${shared_packages[@]}"
            zsh-mac
            aerospace
            sketchybar
        )
    fi

    # Verify all required tools are installed before stowing
    verify_stow_deps "${stow_packages[@]}"

    cd "$DOTFILES_DIR"

    info "Stowing dotfiles with --adopt..."
    for pkg in "${stow_packages[@]}"; do
        if [[ -d "$DOTFILES_DIR/$pkg" ]]; then
            info "  Stowing: $pkg"
            stow --adopt "$pkg" 2>/dev/null || warn "  Failed to stow $pkg, skipping"
        else
            warn "  Package dir not found: $pkg, skipping"
        fi
    done

    info "Restoring dotfiles to git version..."
    git checkout .
    info "Dotfiles restored to git version"
}

# ══════════════════════════════════════════════════════════════
#  macOS Extras
# ══════════════════════════════════════════════════════════════

setup_mac_extras() {
    # Set up NVM directory
    if [[ ! -d "$HOME/.nvm" ]]; then
        mkdir -p "$HOME/.nvm"
        info "Created ~/.nvm directory"
    fi

    # Offer display switcher setup
    if [[ -f "$DOTFILES_DIR/setup-display-switcher.sh" ]]; then
        info "Display switcher available. Run separately if needed:"
        info "  $DOTFILES_DIR/setup-display-switcher.sh --auto"
    fi
}

# ══════════════════════════════════════════════════════════════
#  Main
# ══════════════════════════════════════════════════════════════

main() {
    info "Starting post-install setup from $DOTFILES_DIR"
    info "Detected OS: $OS"

    # ── Package manager ───────────────────────────────────────
    section "Package Manager"
    if [[ "$OS" == "Linux" ]]; then
        install_yay
    elif [[ "$OS" == "Darwin" ]]; then
        install_homebrew
    else
        error "Unsupported OS: $OS"
    fi

    # ── Packages ──────────────────────────────────────────────
    section "Packages"
    if [[ "$OS" == "Linux" ]]; then
        install_packages_linux
    elif [[ "$OS" == "Darwin" ]]; then
        install_packages_mac
    fi

    # ── Shell deps (fzf-tab, atuin) ──────────────────────────
    section "Shell Dependencies"
    install_shell_deps

    # ── Default shell ─────────────────────────────────────────
    section "Default Shell"
    set_default_shell

    # ── Stow ──────────────────────────────────────────────────
    section "Stow Dotfiles"
    stow_dotfiles

    # ── Platform extras ───────────────────────────────────────
    if [[ "$OS" == "Darwin" ]]; then
        section "macOS Extras"
        setup_mac_extras
    fi

    echo ""
    info "Setup complete! Restart your terminal or run: exec zsh"
}

main "$@"
