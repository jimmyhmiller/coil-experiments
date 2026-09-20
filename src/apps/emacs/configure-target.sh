#!/bin/sh
set -eu

here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
source_dir="$here/vendor/emacs"
target_dir="$here/target/darwin-arm64"

cd "$source_dir"
ac_cv_header_stdckdint_h=no \
emacs_cv_func___builtin_frame_address=no \
emacs_cv_func___builtin_unwind_init=no \
./configure \
  --with-x=no \
  --with-ns=no \
  --without-x-toolkit \
  --with-gnutls=ifavailable \
  --without-native-compilation \
  --with-jim \
  CFLAGS='-std=gnu11 -g3 -O2' \
  CPPFLAGS='-I/opt/homebrew/opt/llvm/include -I/opt/homebrew/opt/openssl@3/include' \
  LDFLAGS='-L/opt/homebrew/opt/llvm/lib -L/opt/homebrew/opt/openssl@3/lib'

make -C lib stdckdint.h

git ls-files --others --ignored --exclude-standard \
  | while IFS= read -r file; do
      case "$file" in
        lib/*.h|lib/*.inc|src/*.h|src/*.inc)
          mkdir -p "$target_dir/$(dirname -- "$file")"
          cp "$file" "$target_dir/$file"
          ;;
      esac
    done
