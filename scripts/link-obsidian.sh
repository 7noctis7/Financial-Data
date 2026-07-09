#!/bin/sh
# Lie la documentation du projet (docs/) à un vault Obsidian par lien
# symbolique : les notes restent versionnées dans Git, Obsidian les voit
# (et rend les diagrammes Mermaid nativement).
#
#   ./scripts/link-obsidian.sh "/chemin/vers/mon/vault"
#
# Sans argument, utilise $OBSIDIAN_VAULT s'il est défini.
set -eu

VAULT="${1:-${OBSIDIAN_VAULT:-}}"
if [ -z "$VAULT" ]; then
  echo "usage : $0 \"/chemin/vers/le/vault\"  (ou export OBSIDIAN_VAULT=...)" >&2
  exit 2
fi
if [ ! -d "$VAULT" ]; then
  echo "vault introuvable : $VAULT" >&2
  exit 1
fi

REPO_DOCS="$(cd "$(dirname "$0")/.." && pwd)/docs"
TARGET="$VAULT/Financial Command Center"

if [ -e "$TARGET" ]; then
  echo "existe déjà : $TARGET — rien à faire" >&2
  exit 0
fi
ln -s "$REPO_DOCS" "$TARGET"
echo "lié : $TARGET → $REPO_DOCS"
