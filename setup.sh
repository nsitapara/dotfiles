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

    # ── Post-stow symlinks (platform-agnostic) ────────────
    # eza theme.yml must point to the omarchy current theme.
    # We create this after stow because the target path uses $HOME
    # which differs between macOS (/Users/x) and Linux (/home/x).
    local eza_theme="$HOME/.config/eza/theme.yml"
    local eza_target="$HOME/.config/omarchy/current/eza-theme.yml"
    if [[ -f "$eza_target" || -L "$eza_target" ]]; then
        ln -sf "$eza_target" "$eza_theme"
        info "Linked eza theme.yml -> $eza_target"
    else
        warn "eza theme target not found: $eza_target"
    fi
}

# ══════════════════════════════════════════════════════════════
#  Linux Machine Tweaks (chassis-aware, idempotent)
# ══════════════════════════════════════════════════════════════
#
# Writes Hyprland extras into ~/.local/state/omarchy/toggles/hypr/
# which Omarchy's stock hyprland.conf already glob-sources, so no
# stowed config file is touched. System-level tweaks are applied via
# sudo with grep-guards and timestamped backups.
#
# Non-interactive overrides (set before running):
#   CHASSIS=laptop|desktop
#   WANT_CHROME_AUTOSTART=1|0
# ──────────────────────────────────────────────────────────────

TOGGLES_DIR="$HOME/.local/state/omarchy/toggles/hypr"

prompt_chassis() {
    if [[ -n "${CHASSIS:-}" ]]; then
        info "Chassis (from env): $CHASSIS"
        return
    fi
    echo ""
    echo "What kind of machine is this?"
    select choice in "laptop" "desktop"; do
        case "$choice" in
            laptop|desktop) CHASSIS=$choice; break ;;
            *)              echo "Pick 1 or 2." ;;
        esac
    done
    info "Chassis: $CHASSIS"
}

prompt_chrome_autostart() {
    if [[ -n "${WANT_CHROME_AUTOSTART:-}" ]]; then
        info "Chrome autostart (from env): $WANT_CHROME_AUTOSTART"
        return
    fi
    echo ""
    read -rp "Autostart Google Chrome at login? [y/N] " ans
    if [[ "$ans" =~ ^[Yy]$ ]]; then
        WANT_CHROME_AUTOSTART=1
    else
        WANT_CHROME_AUTOSTART=0
    fi
}

write_hypr_extras() {
    mkdir -p "$TOGGLES_DIR"

    local chrome_conf="$TOGGLES_DIR/10-bootstrap-chrome.conf"
    if [[ "$WANT_CHROME_AUTOSTART" == "1" ]]; then
        cat > "$chrome_conf" <<'EOF'
# Generated by ~/.dotfiles/setup.sh — Chrome autostart at login.
# Delete this file (or re-run setup.sh and answer no) to disable.
exec-once = uwsm-app -- google-chrome-stable
EOF
        info "Wrote $chrome_conf"
    elif [[ -f "$chrome_conf" ]]; then
        rm -f "$chrome_conf"
        info "Removed $chrome_conf (autostart disabled)"
    fi

    local laptop_conf="$TOGGLES_DIR/20-bootstrap-laptop.conf"
    if [[ "$CHASSIS" == "laptop" ]]; then
        cat > "$laptop_conf" <<'EOF'
# Generated by ~/.dotfiles/setup.sh — laptop-only Hyprland overrides.
# Delete this file (or re-run setup.sh as desktop) to disable.

# Disable internal display when lid closes; re-enable on open.
bindl = , switch:on:Lid Switch,  exec, hyprctl keyword monitor "eDP-1, disable"
bindl = , switch:off:Lid Switch, exec, hyprctl keyword monitor "eDP-1, preferred, auto, 1"

# Power button => shutdown (instead of suspend).
unbind = , XF86PowerOff
bindl  = , XF86PowerOff, exec, omarchy-system-shutdown
EOF
        info "Wrote $laptop_conf"
    elif [[ -f "$laptop_conf" ]]; then
        rm -f "$laptop_conf"
        info "Removed $laptop_conf (desktop chassis)"
    fi
}

disable_sddm_autologin() {
    local sddm=/etc/sddm.conf.d/autologin.conf
    if [[ ! -f "$sddm" ]]; then
        info "$sddm not present — skipping"
        return
    fi
    if ! sudo grep -qE '^(User|Session)=' "$sddm" 2>/dev/null; then
        info "SDDM autologin already disabled — skipping"
        return
    fi
    local bak="$sddm.bak.$(date +%Y%m%d-%H%M%S)"
    sudo cp "$sddm" "$bak"
    sudo sed -i -E 's/^(User=|Session=)/#\1/' "$sddm"
    info "Disabled SDDM autologin in $sddm (backup: $bak)"
}

enroll_tpm_luks() {
    local luks_dev
    luks_dev=$(lsblk -o NAME,FSTYPE -nr 2>/dev/null | awk '$2=="crypto_LUKS"{print "/dev/"$1; exit}')
    if [[ -z "$luks_dev" ]]; then
        info "No LUKS device detected — skipping TPM enroll"
        return
    fi
    if ! command -v systemd-cryptenroll &>/dev/null; then
        warn "systemd-cryptenroll not available — skipping TPM enroll"
        return
    fi
    if sudo systemd-cryptenroll "$luks_dev" 2>/dev/null | grep -q tpm2; then
        info "TPM2 already enrolled on $luks_dev — skipping"
        return
    fi
    echo ""
    read -rp "Enroll TPM2 auto-unlock on $luks_dev? (skips LUKS password at boot) [y/N] " ans
    if [[ "$ans" =~ ^[Yy]$ ]]; then
        sudo systemd-cryptenroll --tpm2-device=auto "$luks_dev"
        info "TPM2 enrolled on $luks_dev"
    else
        info "Skipped TPM enroll"
    fi
}

apply_machine_tweaks() {
    prompt_chassis
    prompt_chrome_autostart
    write_hypr_extras
    disable_sddm_autologin
    enroll_tpm_luks
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
    elif [[ "$OS" == "Linux" ]]; then
        section "Linux Machine Tweaks"
        apply_machine_tweaks
    fi

    echo ""
    info "Setup complete! Restart your terminal or run: exec zsh"
}

main "$@"
