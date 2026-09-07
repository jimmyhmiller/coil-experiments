#!/usr/bin/env bash
# A visible end-to-end image demo: build a workspace, snapshot it, boot it
# instantly in a fresh process, then bake it into a self-booting executable.
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"; cd "$root"
coil="${COIL:-coil}"
img="build/work.coilimage"; app="build/workspace-app"
rm -f "$img" "$app"

echo "building the workspace program"
"$coil" build src/experiments/image/workspace_demo.coil -o build/workspace
echo
echo "########## STEP 1: build a workspace and snapshot it (process A) ##########"
./build/workspace run "$img"
echo "  image on disk: $(wc -c < "$img") bytes"
echo
echo "########## STEP 2: boot the image in a brand-new process (process B) ##########"
./build/workspace boot "$img"
echo
echo "########## STEP 3: bake binary + image into ONE self-booting executable ##########"
./build/workspace bake build/workspace "$img" "$app"
echo "  $(ls -l "$app" | awk '{print $1, $5 " bytes", $NF}')"
echo
echo "########## STEP 4: run it with NO arguments — the executable IS the image ##########"
"./$app"
