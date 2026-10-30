#!/bin/sh
set -eu

RECIPES=/share/cooklang/recipes
CONFIG=/data/cookcli
OPTIONS=/data/options.json
STATE=/data/managed-users.tsv
mkdir -p "$RECIPES" "$CONFIG"
chmod 700 "$CONFIG"
export COOK_CONFIG_DIR="$CONFIG"

# Usernames may not contain tabs/newlines; passwords are never logged.
# Only update a password if the configuration actually changed.
NEW_STATE=$(mktemp /data/cookcli-users.XXXXXX)
trap 'rm -f "$NEW_STATE"' EXIT HUP INT TERM
[ -f "$STATE" ] || : > "$STATE"
chmod 600 "$STATE" "$NEW_STATE"

if [ -s "$OPTIONS" ]; then
  ITEMS=$(mktemp /data/cookcli-items.XXXXXX)
  trap 'rm -f "$NEW_STATE" "$ITEMS"' EXIT HUP INT TERM
  jq -rc '.users // [] | .[] | @base64' "$OPTIONS" > "$ITEMS"
  # Each item is base64-encoded to preserve whitespace and punctuation in passwords.
  while IFS= read -r item; do
    username=$(printf '%s' "$item" | base64 -d | jq -r '.username')
    password=$(printf '%s' "$item" | base64 -d | jq -r '.password')
    [ -n "$username" ] && [ -n "$password" ] || { echo 'ERROR: Gebruikersnaam of wachtwoord ontbreekt' >&2; exit 1; }
    fingerprint=$(printf '%s' "$password" | sha256sum | cut -d ' ' -f1)
    previous=$(awk -F '\t' -v u="$username" '$1==u {print $2; exit}' "$STATE")
    if ! cook server user list 2>/dev/null | grep -Fxq -- "$username"; then
      printf '%s\n' "$password" | cook server user add "$username" >/dev/null
      echo "CookCLI: gebruiker toegevoegd: $username"
    elif [ "$fingerprint" != "$previous" ]; then
      printf '%s\n' "$password" | cook server user passwd "$username" >/dev/null
      echo "CookCLI: wachtwoord bijgewerkt: $username"
    fi
    printf '%s\t%s\n' "$username" "$fingerprint" >> "$NEW_STATE"
  done < "$ITEMS"
  rm -f "$ITEMS"
fi
# Do not automatically remove CookCLI accounts omitted in HA options.
# The server's persistent users file remains the source of truth.
[ -s "$NEW_STATE" ] && mv "$NEW_STATE" "$STATE" || true

echo "CookCLI recipes: $RECIPES"
exec cook server "$RECIPES" --host --port 9080
