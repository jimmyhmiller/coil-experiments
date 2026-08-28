#!/bin/sh
set -eu

prompt=$(sed -n '1,$p' "$2")
candidate=$(printf '%s\n' "$prompt" | sed -n 's/.*artifact to `\([^`]*\)`.*/\1/p' | sed -n '1p')
module=$(printf '%s\n' "$prompt" | sed -n 's/.*declare exactly `(module \([^)]*\))`.*/\1/p' | sed -n '1p')
marker="${candidate}.attempt"

attempt=1
if [ -f "$marker" ]; then
  attempt=$(($(sed -n '1p' "$marker") + 1))
fi
printf '%s\n' "$attempt" > "$marker"

if [ "$attempt" -eq 1 ]; then
  printf '(module %s)\n(export answer)\n(defn answer [] (-> i64) missing-name)\n(defn main [] (-> i64) 0)\n' "$module" > "$candidate"
elif [ "$attempt" -eq 2 ]; then
  # Valid alone, invalid through the consumer's public API expectation.
  printf '(module %s)\n(export answer)\n(defn answer [] (-> bool) true)\n(defn main [] (-> i64) 0)\n' "$module" > "$candidate"
else
  printf '(module %s)\n(export answer)\n(defn answer [] (-> i64) 42)\n(defn main [] (-> i64) 0)\n' "$module" > "$candidate"
fi
