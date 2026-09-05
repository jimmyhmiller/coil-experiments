# Emacs through the Coil C reader

This project compiles GNU Emacs through the C reader metaprogram. The pinned
source is Jimmy Miller's Emacs fork, including its all-Coil `jim` window-system
backend. The C frontend receives Emacs's complete configured core and gnulib
translation-unit set in one invocation and lowers it to one Coil module.

The checked-in `target/darwin-arm64` directory is configuration output for the
pinned source revision. It was produced by Emacs's own configure system with
the options recorded in `src/config.h`; configure is not part of the Coil build.
Regenerate it with `./configure-target.sh`. The script declares unsupported
compiler probes explicitly, including VLAs, C23 checked-arithmetic headers, and
stack-unwind builtins, so Emacs selects its portable implementations.

Initialize the source checkout after cloning:

```sh
git submodule update --init src/apps/emacs/vendor/emacs
```

Build the native program:

```sh
cd src/apps/emacs
coil build
```

The first goal is a byte-for-byte faithful tty Emacs executable. The `jim`
window backend then supplies the graphical integration without adding authored
C implementation code.

## Scope

`Coil.toml` lists every object selected by the configured Emacs `src/Makefile`
and every source selected for `libgnu.a`. This is deliberately explicit: when
the C frontend cannot translate a construct, the build reports the source
location and the compatibility work is made in the reusable C dialect.
