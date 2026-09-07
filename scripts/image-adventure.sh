#!/usr/bin/env bash
# A real app on top of images: a text adventure whose whole world is a live
# object graph. Play it, snapshot mid-game, boot the snapshot in a fresh
# process, and bake it into a self-booting game executable. Not Python; a
# harness only.
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"; cd "$root"
coil="${COIL:-coil}"
img="build/adventure.coilimage"; game="build/game"
rm -f "$img" "$game"

echo "building the adventure"
"$coil" build src/experiments/image/adventure.coil -o build/adventure

echo
echo "########## SESSION 1: play, then snapshot the running world ##########"
printf 'n\ntake brass key\ns\ne\ntake loaf of bread\ns\ntake silver coin\nscore\nsave %s\nquit\n' "$img" \
  | ./build/adventure new | sed -n 's/^\(Taken\|Moves\|world snapshotted\).*/  &/p'
echo "  image on disk: $(wc -c < "$img") bytes"

echo
echo "########## SESSION 2: a fresh process boots the world and plays on ##########"
out="$(printf 'score\nw\ntake rusty sword\nscore\nquit\n' | ./build/adventure boot "$img")"
echo "$out" | sed -n 's/^\(World restored\|Taken\|Moves\).*/  &/p'
echo "$out" | grep -q "Score: 24" || { echo "FAIL: expected score 24 after boot+play"; exit 1; }

echo
echo "########## bake binary + world into one self-booting game ##########"
./build/adventure bake build/adventure "$img" "$game" >/dev/null
echo "  $(ls -l "$game" | awk '{print $1, $5" bytes", $NF}')"
selfout="$(printf 'score\nquit\n' | "./$game")"
echo "$selfout" | sed -n 's/^\(This executable\|Moves\).*/  &/p'
echo "$selfout" | grep -q "Score: 16" || { echo "FAIL: baked game did not restore the saved world"; exit 1; }

echo
echo "PASS: a real app's world imaged, booted across processes, and baked into an executable"
