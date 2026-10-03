#!/usr/bin/env python3
"""Restore the saved Quattro configuration without adopting fresh defaults."""

import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile


LINKS = (
    ("hypr", ".config/hypr"),
    ("omarchy", ".config/omarchy"),
    ("omarchy", ".local/state/omarchy/toggles/hypr"),
    ("kitty", ".config/kitty"),
    ("alacritty", ".config/alacritty"),
    ("ghostty", ".config/ghostty"),
)


def run(*args, capture=False):
    return subprocess.run(args, check=True, text=True,
                          stdout=subprocess.PIPE if capture else None).stdout


def link_directory(source, target, backup_root, dry_run=False):
    source, target = Path(source), Path(target)
    if not source.exists():
        raise RuntimeError(f"Saved settings directory is missing: {source}")
    if target.is_symlink() and target.resolve() == source.resolve():
        print(f"Already linked: {target}")
        return False
    print(f"Link: {target} -> {source}")
    if dry_run:
        if target.exists() or target.is_symlink():
            print(f"  Existing settings will be backed up under {backup_root}")
        return True
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() or target.is_symlink():
        backup_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        backup = backup_root / target.name
        if backup.exists() or backup.is_symlink():
            raise RuntimeError(f"Backup already exists: {backup}")
        target.rename(backup)
        print(f"  Backup: {backup}")
    target.symlink_to(os.path.relpath(source, target.parent), target_is_directory=source.is_dir())
    return True


def restore_links(dotfiles, home, backup_root, dry_run=False):
    for package, relative in LINKS:
        link_directory(dotfiles / package / relative, home / relative,
                       backup_root / package / Path(relative).parent, dry_run)
    link_directory(dotfiles / "zsh/.zshrc", home / ".zshrc", backup_root / "zsh", dry_run)


def load_lock(path):
    data = json.loads(path.read_text())
    if data.get("version") != 1:
        raise RuntimeError("Unsupported Omarchy plugin lock format")
    seen = set()
    for plugin in data.get("plugins", []):
        identifier = plugin.get("id", "")
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", identifier) or identifier in seen:
            raise RuntimeError(f"Invalid or duplicate plugin id: {identifier}")
        if not re.fullmatch(r"https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", plugin.get("url", "")):
            raise RuntimeError(f"Invalid saved GitHub URL for {identifier}")
        if not re.fullmatch(r"[0-9a-f]{40}", plugin.get("revision", "")):
            raise RuntimeError(f"Invalid saved revision for {identifier}")
        if plugin.get("branch", "").startswith("-"):
            raise RuntimeError(f"Invalid saved branch for {identifier}")
        seen.add(identifier)
    return data


def restore_plugins(home, lock, dry_run=False):
    directory = home / ".config/omarchy/plugins"
    for plugin in lock["plugins"]:
        target = directory / plugin["id"]
        if target.exists() or target.is_symlink():
            manifest = target / "manifest.json"
            if not manifest.is_file() or json.loads(manifest.read_text()).get("id") != plugin["id"]:
                raise RuntimeError(f"Existing plugin does not match saved id: {target}")
            print(f"Keeping installed plugin: {plugin['id']}")
            continue
        print(f"Restore plugin: {plugin['id']} @ {plugin['revision'][:12]}")
        if dry_run:
            continue
        directory.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".restore-", dir=directory) as temporary:
            stage = Path(temporary) / "plugin"
            run("omarchy-git-url-check", plugin["url"])
            clone = ["git", "clone"]
            if plugin.get("branch"):
                clone += ["--branch", plugin["branch"]]
            run(*clone, "--", plugin["url"], str(stage))
            # Only reset the newly created checkout. Existing plugin edits and
            # updates are never overwritten by a restore run.
            run("git", "-C", str(stage), "reset", "--hard", plugin["revision"])
            run("omarchy", "plugin", "validate", str(stage))
            if json.loads((stage / "manifest.json").read_text()).get("id") != plugin["id"]:
                raise RuntimeError(f"Saved plugin id does not match repository: {plugin['id']}")
            stage.rename(target)


def snapshot_plugins(home, lock_path):
    directory = home / ".config/omarchy/plugins"
    plugins = []
    for folder in sorted(directory.iterdir()):
        if not (folder / "manifest.json").is_file() or not (folder / ".git").exists():
            continue
        def git(*args):
            return run("git", "-C", str(folder), *args, capture=True).strip()
        if git("status", "--porcelain"):
            raise RuntimeError(f"Plugin {folder.name} has local edits; save those before taking a revision snapshot")
        plugins.append({"id": json.loads((folder / "manifest.json").read_text())["id"],
                        "url": git("remote", "get-url", "origin"),
                        "revision": git("rev-parse", "HEAD"),
                        "branch": git("branch", "--show-current")})
    theme_file = home / ".local/state/omarchy/current/theme.name"
    data = {"version": 1, "theme": theme_file.read_text().strip() if theme_file.is_file() else "",
            "plugins": plugins}
    temporary = lock_path.with_name(".plugins.lock.tmp")
    temporary.write_text(json.dumps(data, indent=2) + "\n")
    try:
        load_lock(temporary)
        os.replace(temporary, lock_path)
    finally:
        temporary.unlink(missing_ok=True)
    print(f"Saved {len(plugins)} plugin revisions and the selected theme to {lock_path}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="show the restore without changing files")
    parser.add_argument("--skip-plugins", action="store_true", help="link settings without installing missing plugins")
    parser.add_argument("--skip-theme", action="store_true", help="leave the selected theme unchanged")
    parser.add_argument("--no-reload", action="store_true", help="restore from a TTY and apply on next login")
    parser.add_argument("--snapshot", action="store_true", help="record current third-party revisions and theme")
    args = parser.parse_args(argv)
    dotfiles = Path(__file__).resolve().parent.parent
    home = Path.home()
    lock_path = dotfiles / "omarchy/.config/omarchy/plugins.lock.json"
    if args.snapshot:
        if args.dry_run:
            parser.error("--snapshot cannot be combined with --dry-run")
        snapshot_plugins(home, lock_path)
        return 0
    if sys.platform != "linux" or not shutil.which("omarchy"):
        parser.error("Restore requires an installed Omarchy Quattro system")
    os.environ["OMARCHY_PATH"] = "/usr/share/omarchy"
    lock = load_lock(lock_path)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    backup_root = home / ".local/state/dotfiles-backups/quattro" / stamp
    restore_links(dotfiles, home, backup_root, args.dry_run)
    if not args.skip_plugins:
        restore_plugins(home, lock, args.dry_run)
    if not args.skip_theme and lock.get("theme"):
        theme_file = home / ".local/state/omarchy/current/theme.name"
        current = theme_file.read_text().strip() if theme_file.is_file() else ""
        generated = home / ".local/state/omarchy/current/theme"
        missing_templates = any(not (generated / template.name[:-4]).is_file()
                                for template in (home / ".config/omarchy/themed").glob("*.tpl"))
        if current != lock["theme"]:
            print(f"Restore selected theme: {lock['theme']}")
            if not args.dry_run:
                run("omarchy", "theme", "set", lock["theme"])
        elif missing_templates:
            print("Generate missing user theme templates")
            if not args.dry_run:
                run("env", "OMARCHY_THEME_HEADLESS=1", "OMARCHY_THEME_SKIP_BACKGROUND=1",
                    "omarchy", "theme", "set", lock["theme"])
    eza = home / ".config/eza"
    if eza.is_dir() and not args.dry_run:
        theme_link = eza / "theme.yml"
        expected = home / ".local/state/omarchy/current/theme/eza-theme.yml"
        if theme_link.is_symlink():
            theme_link.unlink()
        elif theme_link.exists():
            backup_root.mkdir(parents=True, exist_ok=True, mode=0o700)
            theme_link.rename(backup_root / "eza-theme.yml")
        theme_link.symlink_to(expected)
    # Upgrade the legacy path in an existing Linux zsh dotfile as well.
    zshrc = home / ".zshrc"
    if not args.dry_run and zshrc.is_file():
        old = "export OMARCHY_PATH=$HOME/.local/share/omarchy"
        content = zshrc.read_text()
        updated = content.replace(old, "export OMARCHY_PATH=/usr/share/omarchy")
        updated = updated.replace("~/.config/omarchy/current/fzf-colors.sh",
                                  "~/.local/state/omarchy/current/theme/fzf-colors.sh")
        if updated != content:
            backup_root.mkdir(parents=True, exist_ok=True, mode=0o700)
            shutil.copy2(zshrc, backup_root / "zshrc")
            zshrc.write_text(updated)
    if not args.no_reload and not args.dry_run:
        run("hyprctl", "reload")
        errors = run("hyprctl", "configerrors", capture=True).strip()
        if errors:
            raise RuntimeError(f"Hyprland configuration errors:\n{errors}")
        run("omarchy", "restart", "shell")
        run("omarchy-shell", "shell", "ping")
    print("Dry run complete; no files changed." if args.dry_run else
          "Quattro settings are linked. Commit and push dotfiles changes to preserve them off this machine.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f"restore-omarchy: {error}", file=sys.stderr)
        raise SystemExit(1)
