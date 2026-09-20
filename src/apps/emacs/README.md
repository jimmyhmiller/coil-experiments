# Emacs through the Coil C reader

This project compiles GNU Emacs through the C reader metaprogram. The pinned
source is Jimmy Miller's Emacs fork, including its all-Coil `jim` window-system
backend. The C frontend receives Emacs's complete configured core and gnulib
translation-unit set in one invocation. This worktree opts into generated-module
partitioning: the reader emits one implementation per C source, one shared
declaration-only type module, and a small public facade. Each implementation is
compiled sequentially in the same compiler process, with its own compiler state,
resettable arenas and LLVM resources. Interfaces and body buffers are owned by
the enclosing generated-program session.

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

Build with the experimental generated-module candidate (not the installed
toolchain):

```sh
cd src/apps/emacs
/path/to/coil-generated-inprocess-facade build --backend llvm
```

LLVM is currently required for C exports with by-value aggregate parameters;
the direct AArch64 backend reports that its marshaling thunk is not implemented.
The complete 163-source LLVM build now links, reports GNU Emacs 30.2.50 with
`--version`, runs a bare batch Lisp file using `--batch --no-loadup -l`, and passes
normal `--batch --quick --eval` with the upstream-generated assets below.
The in-process O0 build takes 680.291 seconds and peaks at 8,813,002,752 bytes
RSS. All 163 C sources are compiled, and the linked artifact passes version,
bare-batch and normal quick-batch smokes with the assets below. The quick-batch
probe prints `42`, exits zero and takes 158.584 seconds with O0 source-Lisp startup.
The emitting facade closes its compiler state before the first owner starts;
completed owners release their state too. Interfaces, remaining body buffers,
normalized configuration and artifacts have the enclosing program lifetime.
The largest pure-storage initializer still has a large working set.

Before the facade lifetime split, the correct in-process build took 846.405
seconds and peaked at 10,751,262,720 bytes. The resulting executable is unchanged
(SHA-256 `d79261d9139b4a2df17bff466527088618a9c2dedb2909610ec3d20dad383910`).
For comparison, the superseded subprocess implementation took 783.799 seconds
and peaked at 10,184,163,328 bytes for its process tree. The newest in-process
run improves both figures, but these are individual development measurements,
not a controlled benchmark. No optimized or dumped runtime-performance claim
follows from the startup smoke tests.

From the workspace root, the development-only measurement harness captures
compiler logs, wall time, and the complete live process-tree RSS at 100 ms
intervals:

```sh
python3 scripts/c-emacs-memory.py --compiler /path/to/coil-generated-inprocess-facade --backend llvm
```

## Bootstrap data and Lisp

An undumped executable needs the pinned source's charset maps, Unicode tables,
loaddefs, and DOC file. Generate these using Emacs's own make targets in a private source copy;
do not hand-author replacement assets or commit generated upstream files. A
working bootstrap Emacs is needed for the autoload target (Emacs 30.1 was used
to generate the pinned 30.2 source's loaddefs in this experiment).

Starting in this application directory, with the configured vendor checkout:

```sh
asset_root=$(mktemp -d /private/tmp/emacs-bootstrap-assets-XXXXXX)
cp -R vendor/emacs "$asset_root/source"
cd "$asset_root/source"
make -j4 -C admin/charsets all
make -j4 -C lisp EMACS=/path/to/bootstrap/emacs \
  "EMACSOPT=-Q --batch --eval '(setq lisp-directory \"$asset_root/source/lisp/\")'" autoloads
make -j4 -C admin/unidata EMACS=/path/to/bootstrap/emacs \
  "emacs=\"/path/to/bootstrap/emacs\" -Q --batch -L $asset_root/source/lisp/international --eval '(setq source-directory \"$asset_root/source/\" lisp-directory \"$asset_root/source/lisp/\" data-directory \"$asset_root/source/etc/\")'" all
make -j4 -C lib-src make-docfile
make -j8 -C src ../etc/DOC
```

The explicit private `lisp-directory` is important: an installed bootstrap Emacs
otherwise retains its own installation's output directory. Upstream make may
rerun configuration and compile native prerequisites for `make-docfile` and DOC
in this private copy; these are build helpers, not the translated executable.

Point the translated executable at those directories using Emacs's normal
process-scoped configuration:

```sh
EMACSLOADPATH="$asset_root/source/lisp" \
EMACSPATH="$asset_root/source/lib-src" \
EMACSDATA="$asset_root/source/etc" \
EMACSDOC="$asset_root/source/etc" \
  /path/to/translated/emacs --batch --quick --eval '(princ (+ 20 22))'
```

The development smoke harness verifies version, bare batch, and normal quick
batch separately, retaining exit statuses and both output streams:

```sh
python3 scripts/c-emacs-smoke.py --emacs /path/to/translated/emacs \
  --assets-root "$asset_root/source" --output /path/to/smoke-results
```

The first goal is a byte-for-byte faithful tty Emacs executable. The `jim`
window backend then supplies the graphical integration without adding authored
C implementation code.

## Scope

`Coil.toml` lists every object selected by the configured Emacs `src/Makefile`
and every source selected for `libgnu.a`. This is deliberately explicit: when
the C frontend cannot translate a construct, the build reports the source
location and the compatibility work is made in the reusable C dialect.
