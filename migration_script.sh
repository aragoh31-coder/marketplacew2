#!/usr/bin/env bash
set -euo pipefail

BACKUP_DIR="theme_migration_backup"
NEW_THEME_DIR="new_theme"

usage() {
  echo "Usage: $0 apply|revert"
  exit 1
}

if [ $# -ne 1 ]; then
  usage
fi

COMMAND=$1

case "$COMMAND" in
  apply)
    if [ -d "$BACKUP_DIR" ]; then
      echo "Backup directory '$BACKUP_DIR' already exists. Aborting to avoid overwriting."
      exit 1
    fi
    echo "Creating backup directory '$BACKUP_DIR'..."
    mkdir "$BACKUP_DIR"

    echo "Backing up existing templates and static files..."
    cp -r templates "$BACKUP_DIR/"
    cp -r static/css "$BACKUP_DIR/static_css"

    echo "Applying new theme..."
    cp -r "$NEW_THEME_DIR/templates/"* templates/
    cp -r "$NEW_THEME_DIR/static/css/"* static/css/

    echo "New theme applied. If you don't like it, run '$0 revert' to restore your original design."
    ;;
  revert)
    if [ ! -d "$BACKUP_DIR" ]; then
      echo "Backup directory '$BACKUP_DIR' not found. Cannot revert."
      exit 1
    fi
    echo "Reverting to original design..."
    rm -rf templates
    rm -rf static/css
    mv "$BACKUP_DIR/templates" .
    mkdir -p static
    mv "$BACKUP_DIR/static_css" static/css

    echo "Reversion complete. You can safely remove '$BACKUP_DIR'."
    ;;
  *)
    usage
    ;;
esac
