#!/bin/sh
set -eu

project_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
output_dir="$project_dir/builds/native-live-demo"
coil_bin=${COIL:-coil}
mkdir -p "$output_dir"

cd "$project_dir"
"$coil_bin" build src/experiments/heap-inspector/native_demo.coil -o "$output_dir/native-live-demo"
exec "$output_dir/native-live-demo"
