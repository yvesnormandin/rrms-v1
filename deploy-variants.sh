#!/usr/bin/env bash
# deploy-variants.sh — regenerate + push the GTP demo variants from the
# canonical app source (cxas_app/rrms-v1).
#
# Each variant is byte-identical to canonical except:
#   - DEFAULT_CALLER_PHONE in the before_agent callback (the variant's demo CLID)
#   - app.json name/displayName (the variant's identity on the platform)
#   - app.json fields from `appConfigOverrides` in deploy-variants.json, deep-
#     merged in before push. This is how Console-only "advanced settings" that
#     a plain push would otherwise RESET — Cloud Logging, BigQuery export, live
#     audio-recording bucket (all under loggingSettings) — are preserved on
#     every deploy. The repo is the source of truth; edit the values there.
#
# Usage:
#   ./deploy-variants.sh             # deploy all variants from deploy-variants.json
#   ./deploy-variants.sh --dry-run   # show what would be pushed, push nothing
#
# First run per variant (app_id null) creates the app via --display-name and
# writes the returned app_id back into deploy-variants.json. Subsequent runs
# push in place (--to), so GTP number wiring in the Console is never disturbed.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
CONFIG="$ROOT/deploy-variants.json"
VENV="/home/norman/dev/cxas-scrapi/.venv"
CXAS="$VENV/bin/cxas"
PY="$VENV/bin/python"
DRY_RUN="${1:-}"

PROJECT=$("$PY" -c "import json;print(json.load(open('$CONFIG'))['gcp_project_id'])")
LOCATION=$("$PY" -c "import json;print(json.load(open('$CONFIG'))['location'])")
SRC="$ROOT/$("$PY" -c "import json;print(json.load(open('$CONFIG'))['canonical_app_dir'])")"
CB_REL=$("$PY" -c "import json;print(json.load(open('$CONFIG'))['callback_file'])")
N=$("$PY" -c "import json;print(len(json.load(open('$CONFIG'))['variants']))")
COMMIT=$(git -C "$ROOT" rev-parse --short HEAD 2>/dev/null || echo "no-git")

echo "Deploying $N variant(s) from $SRC (canonical @ $COMMIT)"

for ((i=0; i<N; i++)); do
  NAME=$("$PY" -c "import json;print(json.load(open('$CONFIG'))['variants'][$i]['name'])")
  CLID=$("$PY" -c "import json;print(json.load(open('$CONFIG'))['variants'][$i]['clid'])")
  APP_ID=$("$PY" -c "import json;v=json.load(open('$CONFIG'))['variants'][$i];print(v['app_id'] or '')")

  TMP=$(mktemp -d)
  trap 'rm -rf "$TMP"' EXIT
  cp -r "$SRC" "$TMP/$NAME"

  # Guard: strip any nested app copies (stale `cxas pull` artifacts — a pull
  # into the app dir creates <app>/<app-name>/ with its own app.json).
  for d in "$TMP/$NAME"/*/; do
    if [[ -f "$d/app.json" ]]; then
      echo "   WARNING: removing nested app artifact ${d#"$TMP/$NAME/"} from variant copy"
      rm -rf "$d"
    fi
  done

  # 1. Substitute the variant's demo CLID (the ONLY code difference).
  CB="$TMP/$NAME/$CB_REL"
  if ! grep -q '^DEFAULT_CALLER_PHONE = ' "$CB"; then
    echo "ERROR: DEFAULT_CALLER_PHONE not found in $CB_REL — aborting." >&2; exit 1
  fi
  sed -i "s/^DEFAULT_CALLER_PHONE = .*/DEFAULT_CALLER_PHONE = \"$CLID\"/" "$CB"
  grep -q "DEFAULT_CALLER_PHONE = \"$CLID\"" "$CB" || { echo "ERROR: substitution failed" >&2; exit 1; }

  # 2. Variant identity in app.json (displayName; name set to app_id when known).
  "$PY" - "$TMP/$NAME/app.json" "$NAME" "$APP_ID" <<'PYEOF'
import json, sys
path, name, app_id = sys.argv[1], sys.argv[2], sys.argv[3]
d = json.load(open(path))
d['displayName'] = name
if app_id:
    d['name'] = app_id
else:
    d.pop('name', None)
json.dump(d, open(path, 'w'), indent=2)
PYEOF

  # 3. Deep-merge appConfigOverrides (from deploy-variants.json) into app.json.
  #    Preserves Console-only "advanced settings" (Cloud Logging, BigQuery
  #    export, live audio-recording bucket) that a plain push would reset. A
  #    per-variant `appConfigOverrides` block, when present, is merged AFTER and
  #    wins over the shared top-level one. No-op when neither is set.
  "$PY" - "$TMP/$NAME/app.json" "$CONFIG" "$i" <<'PYEOF'
import json, sys
app_path, cfg_path, idx = sys.argv[1], sys.argv[2], int(sys.argv[3])
app = json.load(open(app_path))
cfg = json.load(open(cfg_path))

def deep_merge(base, over):
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            deep_merge(base[k], v)
        else:
            base[k] = v

for ov in (cfg.get("appConfigOverrides"),
           cfg["variants"][idx].get("appConfigOverrides")):
    if ov:
        deep_merge(app, ov)

json.dump(app, open(app_path, "w"), indent=2)
PYEOF

  echo "── $NAME  (CLID $CLID, app_id ${APP_ID:-<create>})"
  if [[ "$DRY_RUN" == "--dry-run" ]]; then
    echo "   dry-run: would push $TMP/$NAME"
    grep "^DEFAULT_CALLER_PHONE" "$CB" | sed 's/^/   /'
    echo "   merged loggingSettings:"
    "$PY" -c "import json;print(json.dumps(json.load(open('$TMP/$NAME/app.json')).get('loggingSettings',{}),indent=2))" | sed 's/^/     /'
    rm -rf "$TMP"; trap - EXIT
    continue
  fi

  if [[ -z "$APP_ID" ]]; then
    OUT=$("$CXAS" push --app-dir "$TMP/$NAME" --display-name "$NAME" \
          --project-id "$PROJECT" --location "$LOCATION" 2>&1 | tail -1)
    echo "   $OUT"
    NEW_ID=$(echo "$OUT" | grep -oE 'apps/[a-f0-9-]+' | cut -d/ -f2 || true)
    if [[ -z "$NEW_ID" ]]; then echo "ERROR: could not parse new app id" >&2; exit 1; fi
    "$PY" - "$CONFIG" "$i" "$NEW_ID" <<'PYEOF'
import json, sys
path, idx, app_id = sys.argv[1], int(sys.argv[2]), sys.argv[3]
d = json.load(open(path))
d['variants'][idx]['app_id'] = app_id
json.dump(d, open(path, 'w'), indent=2)
open(path, 'a').write('\n')
PYEOF
    echo "   created app_id $NEW_ID (recorded in deploy-variants.json)"
  else
    "$CXAS" push --app-dir "$TMP/$NAME" \
      --to "projects/$PROJECT/locations/$LOCATION/apps/$APP_ID" \
      --project-id "$PROJECT" --location "$LOCATION" 2>&1 | tail -1 | sed 's/^/   /'
  fi
  echo "   deployed canonical commit: $COMMIT"
  rm -rf "$TMP"; trap - EXIT
done

echo "Done."
