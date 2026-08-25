#!/usr/bin/env python3
"""CoilRS source converter.

The lossless representation is intentionally implemented first: native Coil is
embedded in a lexical `coil { ... }` escape, and the reader extracts it without
changing a byte.  The structured Rust-like parser grows behind the same CLI.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import shutil
import sys

from structured import ParseError, parse as parse_structured
from native import NativeParseError, render_program


class CoilRSError(ValueError):
    pass


def _skip_space_and_comments(source: str, pos: int) -> int:
    n = len(source)
    while pos < n:
        if source[pos].isspace():
            pos += 1
        elif source.startswith("//", pos):
            end = source.find("\n", pos + 2)
            pos = n if end < 0 else end + 1
        elif source.startswith("/*", pos):
            depth = 1
            pos += 2
            while depth and pos < n:
                if source.startswith("/*", pos):
                    depth += 1
                    pos += 2
                elif source.startswith("*/", pos):
                    depth -= 1
                    pos += 2
                else:
                    pos += 1
            if depth:
                raise CoilRSError("unterminated block comment")
        else:
            break
    return pos


def _whole_native_escape(source: str) -> str | None:
    """Return the payload when SOURCE is exactly one `coil { ... }` escape.

    Braces in Coil strings, C strings, character literals and line comments do
    not terminate the escape. Parentheses/brackets are irrelevant here; the
    native reader validates those after extraction.
    """

    pos = _skip_space_and_comments(source, 0)
    if not source.startswith("coil", pos):
        return None
    after = pos + 4
    if after < len(source) and (source[after].isalnum() or source[after] in "_?!-"):
        return None
    after = _skip_space_and_comments(source, after)
    if after >= len(source) or source[after] != "{":
        return None

    payload_start = after + 1
    # Native Coil permits arbitrary symbol spellings, including `{` and `}`.
    # Since this is a whole-file escape, the unambiguous delimiter is the final
    # closing brace followed only by CoilRS whitespace/comments. This also makes
    # from_coil/to_coil exact for every possible native token stream.
    close = source.rfind("}")
    if close < payload_start:
        raise CoilRSError("unterminated `coil { ... }` escape")
    if _skip_space_and_comments(source, close + 1) != len(source):
        return None
    return source[payload_start:close]


def to_coil(source: str, path: str = "<input>") -> str:
    native = _whole_native_escape(source)
    if native is not None:
        return native
    try:
        return parse_structured(source)
    except ParseError as error:
        raise CoilRSError(f"{path}: {error}") from error


def from_coil(source: str, pretty: bool = False, structured_pretty: bool = False) -> str:
    # Preserve the payload byte-for-byte. A newline before the closing delimiter
    # prevents a final native line comment from swallowing it.
    if pretty:
        if structured_pretty:
            try:
                rendered = render_program(source)
                # The renderer is deliberately conservative. Validate its own
                # output before committing to structured syntax so any shape
                # not yet understood falls back losslessly at file granularity.
                parse_structured(rendered)
                return rendered
            except (NativeParseError, ParseError):
                # Compiler repositories intentionally contain malformed reader
                # fixtures. Total conversion still applies: preserve such a
                # file as one native escape instead of rejecting the tree.
                payload = source if not source or source.endswith("\n") else source + "\n"
                return "coil {" + payload + "}\n"
        match = MODULE_RE.search(source)
        if match is not None:
            module = "::".join(
                segment
                if re.fullmatch(r"[@A-Za-z_][A-Za-z0-9_?!-]*", segment)
                else f"`{segment}`"
                for segment in match.group(1).split(".")
            )
            remainder = (source[: match.start()] + source[match.end() :]).strip("\n")
            return f"module {module};\n\ncoil_item {{\n{remainder}\n}}\n"
    if source and not source.endswith("\n"):
        source += "\n"
    # Keep the opening delimiter adjacent to the payload so extraction is a
    # byte-for-byte inverse even when the original deliberately starts with a
    # newline. The source's own final newline separates a trailing `;;` comment
    # from the closing brace.
    return "coil {" + source + "}\n"


def _read(path: str) -> str:
    if path == "-":
        return sys.stdin.read()
    return Path(path).read_text()


SKIP_TREE_DIRS = {
    ".git",
    ".coil",
    ".claude",
    ".agents",
    "build",
    "builds",
    "target",
    "__pycache__",
}
MODULE_RE = re.compile(r"^\s*\(module\s+([^\s()]+)\s*\)", re.MULTILINE)


def _module_stub(source: str, path: Path) -> str | None:
    match = MODULE_RE.search(source)
    if match is None:
        return None
    return (
        f"(module {match.group(1)})\n"
        ";; CoilRS namespace-index stub. The reader materializes this module\n"
        ";; from the adjacent .coilrs source before imports are loaded.\n"
    )


def _tree_files(root: Path):
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if any(part in SKIP_TREE_DIRS for part in relative.parts):
            continue
        yield path


def convert_tree(
    command: str,
    source_root: Path,
    destination_root: Path,
    install_reader: bool = False,
    pretty: bool = False,
    structured_pretty: bool = False,
) -> int:
    """Convert a source tree while preserving all non-source support files."""
    if not source_root.is_dir():
        raise CoilRSError(f"{source_root}: not a directory")
    if destination_root.exists():
        raise CoilRSError(f"{destination_root}: destination already exists")
    converted = 0
    for source_path in _tree_files(source_root):
        relative = source_path.relative_to(source_root)
        destination_path = destination_root / relative
        if source_path.is_dir():
            destination_path.mkdir(parents=True, exist_ok=True)
            continue
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        if command == "from-coil-tree" and source_path.suffix == ".coil":
            destination_path = destination_path.with_suffix(".coilrs")
            native = source_path.read_text()
            try:
                converted_source = from_coil(
                    native, pretty=pretty, structured_pretty=structured_pretty
                )
            except CoilRSError as error:
                raise CoilRSError(f"{source_path}: {error}") from error
            destination_path.write_text(converted_source)
            stub = _module_stub(native, source_path)
            if stub is not None:
                destination_path.with_suffix(".coil").write_text(stub)
            converted += 1
        elif command == "to-coil-tree" and source_path.suffix == ".coilrs":
            destination_path = destination_path.with_suffix(".coil")
            destination_path.write_text(to_coil(source_path.read_text(), str(source_path)))
            converted += 1
        else:
            shutil.copy2(source_path, destination_path)
    if command == "from-coil-tree" and install_reader:
        dialect_source = Path(__file__).resolve().parent
        dialect_destination = destination_root / "src" / "dialects" / "rust"
        dialect_destination.mkdir(parents=True, exist_ok=True)
        for name in (
            "Coil.toml", "rust.coil", "reader.coil", "coilrs.py", "structured.py", "native.py"
        ):
            shutil.copy2(dialect_source / name, dialect_destination / name)
        (destination_root / ".coilrs-tree").write_text(
            "Generated CoilRS tree. Reader import materialization is enabled here.\n"
        )
    return converted


def _find_materialization_root(path: Path) -> Path | None:
    resolved = path.resolve()
    for parent in (resolved.parent, *resolved.parents):
        if (parent / ".coilrs-tree").is_file() and (
            parent / "src/dialects/rust/coilrs.py"
        ).is_file():
            return parent
    return None


def materialize_tree(entry_path: Path) -> int:
    root = _find_materialization_root(entry_path)
    if root is None:
        return 0
    converted = 0
    for source_path in _tree_files(root):
        if source_path.suffix != ".coilrs":
            continue
        native = to_coil(source_path.read_text(), str(source_path))
        destination = source_path.with_suffix(".coil")
        temporary = destination.with_suffix(".coil.tmp")
        temporary.write_text(native)
        temporary.replace(destination)
        converted += 1
    return converted


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="coilrs")
    parser.add_argument(
        "command",
        choices=("to-coil", "from-coil", "roundtrip", "from-coil-tree", "to-coil-tree"),
    )
    parser.add_argument("path")
    parser.add_argument("destination", nargs="?")
    parser.add_argument("--install-reader", action="store_true")
    parser.add_argument("--materialize-tree", action="store_true")
    parser.add_argument("--materialize-entry")
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--structured-pretty", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command.endswith("-tree"):
            if args.destination is None:
                parser.error(f"{args.command} requires DESTINATION")
            count = convert_tree(
                args.command,
                Path(args.path),
                Path(args.destination),
                install_reader=args.install_reader,
                pretty=args.pretty or args.structured_pretty,
                structured_pretty=args.structured_pretty,
            )
            print(f"converted {count} source files", file=sys.stderr)
            return 0
        if args.destination is not None:
            parser.error("DESTINATION is only valid for tree conversion")
        source = _read(args.path)
        if args.command == "to-coil":
            materialize_path = args.materialize_entry or (
                args.path if args.materialize_tree and args.path != "-" else None
            )
            if materialize_path is not None:
                materialize_tree(Path(materialize_path))
            out = to_coil(source, args.path)
        elif args.command == "from-coil":
            out = from_coil(
                source,
                pretty=args.pretty or args.structured_pretty,
                structured_pretty=args.structured_pretty,
            )
        else:
            out = to_coil(from_coil(source), args.path)
        sys.stdout.write(out)
        return 0
    except (OSError, CoilRSError) as error:
        print(f"coilrs: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
