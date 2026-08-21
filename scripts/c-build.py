#!/usr/bin/env python3
"""Compile multiple C translation units together through the native Coil frontend."""
from __future__ import annotations

import argparse
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src/dialects/c"))
import c_ast_to_coil as frontend  # noqa: E402


class BuildError(Exception):
    pass


def project_declarations(ast: dict, roots: tuple[str, ...]) -> list[dict]:
    declarations = frontend.children(ast)
    start = next((i for i, node in enumerate(declarations)
                  if ((node.get("loc") or {}).get("file") or "").startswith(roots)), len(declarations))
    result = []
    in_project = False
    for node in declarations[start:]:
        explicit_file = (node.get("loc") or {}).get("file")
        if explicit_file:
            in_project = explicit_file.startswith(roots)
        if in_project:
            result.append(node)
    return result


def has_body(node: dict) -> bool:
    return bool(frontend.children(node, "CompoundStmt"))


def canonical_type(node: dict) -> str:
    spelling = (node.get("type") or {}).get("desugaredQualType") or (node.get("type") or {}).get("qualType", "")
    spelling = re.sub(r"\b(const|volatile|restrict|_Atomic)\b", "", spelling)
    spelling = re.sub(r"__attribute__\s*\(\([^)]*\)\)", "", spelling)
    return re.sub(r"\s+", " ", spelling).strip()


def layout_attributes(node: dict) -> tuple[str, ...]:
    relevant = {"PackedAttr", "AlignedAttr", "MaxFieldAlignmentAttr", "MSStructAttr"}
    return tuple(sorted(child.get("kind") for child in node.get("inner", [])
                        if child.get("kind") in relevant))


def type_descriptor(node: dict, types: dict[tuple[str, str], dict], stack=()) -> tuple:
    spelling = canonical_type(node)
    referenced = []
    for kind, tag in re.findall(r"\b(struct|union|enum)\s+([A-Za-z_]\w*)", spelling):
        key = (kind, tag)
        definition = types.get(key)
        if definition is None:
            referenced.append((kind, tag, "opaque"))
        elif key in stack:
            referenced.append((kind, tag, "recursive"))
        elif kind == "enum":
            values = []
            value = -1
            for constant in frontend.children(definition, "EnumConstantDecl"):
                explicit = frontend.children(constant, "ConstantExpr")
                value = int(explicit[0].get("value")) if explicit else value + 1
                values.append((constant.get("name"), value))
            referenced.append((kind, tag, tuple(values)))
        else:
            fields = []
            for field in frontend.children(definition, "FieldDecl"):
                width = next((child.get("value") for child in frontend.children(field)
                              if child.get("value") is not None), None) if field.get("isBitfield") else None
                fields.append((field.get("name", ""),
                               type_descriptor(field, types, stack + (key,)), width,
                               layout_attributes(field)))
            referenced.append((kind, tag, layout_attributes(definition), tuple(fields)))
    return spelling, tuple(referenced)


def walk(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


def rename_internal_symbols(ast: dict, declarations: list[dict], unit: int) -> tuple[dict | None, str | None]:
    rename_by_id = {}
    main = None
    main_original_type = None
    for node in declarations:
        if node.get("kind") not in ("FunctionDecl", "VarDecl") or not node.get("name"):
            continue
        if node.get("kind") == "FunctionDecl" and node.get("name") == "main" and has_body(node):
            main = node
            main_original_type = canonical_type(node)
            rename_by_id[node.get("id")] = "__c_user_main"
        elif node.get("storageClass") == "static":
            rename_by_id[node.get("id")] = f"__tu{unit}_{frontend.name(node)}"
    for node in walk(ast):
        node_id = node.get("id")
        if node_id in rename_by_id and node.get("kind") in ("FunctionDecl", "VarDecl"):
            node["name"] = rename_by_id[node_id]
        referenced = node.get("referencedDecl")
        if isinstance(referenced, dict) and referenced.get("id") in rename_by_id:
            referenced["name"] = rename_by_id[referenced["id"]]
    return main, main_original_type


def add_declaration(seen: dict[str, tuple[tuple, pathlib.Path]], kind: str, name: str,
                    signature: tuple, source: pathlib.Path) -> None:
    key = f"{kind}:{name}"
    previous = seen.get(key)
    if previous and previous[0] != signature:
        raise BuildError(f"incompatible declarations for {name}: {previous[0][0]} in {previous[1]} vs {signature[0]} in {source}")
    seen[key] = (signature, source)


def merge_fragment(lines: list[str], fragment: str, declarations: dict[str, str]) -> None:
    for line in fragment.splitlines():
        match = re.match(r"\((defstruct|extern)\s+([^\s\[]+)", line)
        if match:
            key = f"{match.group(1)}:{match.group(2)}"
            previous = declarations.get(key)
            if previous is not None:
                if previous != line:
                    raise BuildError(f"generated declarations disagree for {match.group(2)}")
                continue
            declarations[key] = line
        lines.append(line)


def compile_program(sources: list[pathlib.Path], output: pathlib.Path, cflags: list[str],
                    link_flags: list[str], optimization: str, build_dir: pathlib.Path) -> None:
    root_paths = {source.parent.resolve() for source in sources}
    for flag in cflags:
        if flag.startswith("-I") and len(flag) > 2:
            include = pathlib.Path(flag[2:])
            root_paths.add((ROOT / include).resolve() if not include.is_absolute() else include.resolve())
    project_roots = tuple(str(path).rstrip("/") + "/" for path in sorted(root_paths, key=str))
    asts = []
    project_nodes = []
    for source in sources:
        try:
            ast = frontend.load_ast(str(source), cflags)
        except frontend.Error as error:
            raise BuildError(f"{source}: {error}") from error
        asts.append(ast)
        project_nodes.append(project_declarations(ast, project_roots))

    declarations = {}
    function_definitions: dict[str, tuple[int, dict]] = {}
    global_candidates: dict[str, list[tuple[int, dict, bool]]] = {}
    record_shapes: dict[str, dict[tuple, set[int]]] = {}
    type_indices = []
    for nodes in project_nodes:
        index = {}
        for node in walk(nodes):
            kind = node.get("kind")
            tag = node.get("name")
            if kind in ("RecordDecl", "EnumDecl") and tag and (kind == "EnumDecl" or node.get("completeDefinition")):
                index[(node.get("tagUsed", "enum"), tag)] = node
        type_indices.append(index)
    for unit, (source, nodes) in enumerate(zip(sources, project_nodes)):
        for node in nodes:
            kind = node.get("kind")
            symbol = node.get("name")
            if kind == "FunctionDecl" and symbol and node.get("storageClass") != "static":
                add_declaration(declarations, "function", symbol, type_descriptor(node, type_indices[unit]), source)
                if has_body(node):
                    previous = function_definitions.get(symbol)
                    if previous:
                        raise BuildError(f"multiple definitions of {symbol}: {sources[previous[0]]} and {source}")
                    function_definitions[symbol] = (unit, node)
            elif kind == "VarDecl" and symbol and node.get("storageClass") != "static":
                add_declaration(declarations, "global", symbol, type_descriptor(node, type_indices[unit]), source)
                initializer = bool(frontend.children(node))
                if node.get("storageClass") != "extern" or initializer:
                    global_candidates.setdefault(symbol, []).append((unit, node, initializer))
        for (kind, tag), node in type_indices[unit].items():
            if kind in ("struct", "union"):
                descriptor = type_descriptor({"type": {"qualType": f"{kind} {tag}"}}, type_indices[unit])
                record_shapes.setdefault(frontend.name(node), {}).setdefault(descriptor, set()).add(unit)

    linked_functions = set(function_definitions)
    linked_globals = set(global_candidates)
    for unit, (source, ast) in enumerate(zip(sources, asts)):
        for node in frontend.children(ast):
            symbol = node.get("name")
            if node.get("kind") == "FunctionDecl" and symbol in linked_functions and node.get("storageClass") != "static":
                add_declaration(declarations, "function", symbol, type_descriptor(node, type_indices[unit]), source)
            elif node.get("kind") == "VarDecl" and symbol in linked_globals and node.get("storageClass") != "static":
                add_declaration(declarations, "global", symbol, type_descriptor(node, type_indices[unit]), source)

    main_definition = function_definitions.get("main")
    if main_definition is None:
        raise BuildError("the translation units do not define main")
    for symbol, (owner, definition) in function_definitions.items():
        if definition.get("variadic") and any(
            unit != owner and any(node.get("kind") == "FunctionDecl" and node.get("name") == symbol
                                  for node in nodes)
            for unit, nodes in enumerate(project_nodes)
        ):
            raise BuildError(f"cross-unit calls to C-defined variadic function {symbol} are not yet supported")

    global_owners = {}
    for symbol, candidates in global_candidates.items():
        initialized = [candidate for candidate in candidates if candidate[2]]
        if len(initialized) > 1:
            locations = ", ".join(str(sources[candidate[0]]) for candidate in initialized)
            raise BuildError(f"multiple initialized definitions of {symbol}: {locations}")
        global_owners[symbol] = initialized[0] if initialized else candidates[0]

    record_names = [dict() for _ in sources]
    for symbol, shapes in record_shapes.items():
        if len(shapes) == 1:
            for unit in next(iter(shapes.values())):
                record_names[unit][symbol] = symbol
        else:
            for units in shapes.values():
                for unit in units:
                    record_names[unit][symbol] = f"__tu{unit}_{symbol}"

    main_nodes = []
    main_types = []
    for unit, (ast, nodes) in enumerate(zip(asts, project_nodes)):
        main_node, main_type = rename_internal_symbols(ast, nodes, unit)
        main_nodes.append(main_node)
        main_types.append(main_type)

    generated = []
    generators = []
    for unit, (source, ast) in enumerate(zip(sources, asts)):
        function_targets = {symbol: f"c_{symbol}" for symbol, (owner, _) in function_definitions.items()
                            if owner != unit and symbol != "main"}
        global_targets = {symbol: f"__c_global_{symbol}" for symbol, owner in global_owners.items()
                          if owner[0] != unit}
        owned_global_ids = {owner[1].get("id") for owner in global_owners.values() if owner[0] == unit}
        generator = frontend.Gen(
            ast, str(source), module_name="c_program", standalone=True,
            function_targets=function_targets, global_targets=global_targets,
            owned_external_global_ids=owned_global_ids, wrap_main=False, fragment=unit != 0,
            anonymous_prefix=f"tu{unit}_", record_names=record_names[unit], project_roots=root_paths,
        )
        try:
            generated.append(generator.generate())
        except frontend.Error as error:
            raise BuildError(f"{source}: {error}") from error
        generators.append(generator)

    output_lines = generated[0].splitlines()
    emitted = {}
    for line in output_lines:
        match = re.match(r"\((defstruct|extern)\s+([^\s\[]+)", line)
        if match:
            emitted[f"{match.group(1)}:{match.group(2)}"] = line
    for fragment in generated[1:]:
        merge_fragment(output_lines, fragment, emitted)

    main_unit = main_definition[0]
    main_node = main_nodes[main_unit]
    if main_node is None:
        raise BuildError("internal error: main definition disappeared during translation")
    main_generator = generators[main_unit]
    parameters = frontend.children(main_node, "ParmVarDecl")
    if len(parameters) not in (0, 2, 3):
        raise BuildError("main must take zero, two, or three parameters")
    parameter_types = [main_generator.typ(parameter.get("type")) for parameter in parameters]
    parameter_names = [f"__c_arg{i}" for i in range(len(parameters))]
    arguments = " ".join(f"({name} {typ})" for name, typ in zip(parameter_names, parameter_types))
    call_arguments = " ".join(parameter_names)
    return_spelling = (main_type := main_types[main_unit] or "int ()").split("(", 1)[0].strip()
    return_type = main_generator.typ({"qualType": return_spelling})
    user_main = "c___c_user_main"
    initialized_globals = [f"__c_global_{symbol}" for generator in generators
                           for symbol, node in generator.globals.items() if frontend.children(node)]
    constructors = [constructor for generator in generators for constructor in generator.constructors]
    destructors = [destructor for generator in reversed(generators) for destructor in reversed(generator.destructors)]
    initialize = " ".join(f"({accessor})" for accessor in initialized_globals)
    before = " ".join(filter(None, (initialize, " ".join(f"({constructor})" for constructor in constructors))))
    after = " ".join(f"({destructor})" for destructor in destructors)
    call = f"({user_main}{' ' if call_arguments else ''}{call_arguments})"
    if return_type == "void":
        body = f"(do {before} {call} {after} (primitive/cast i32 0))"
        root_return = "i32"
    else:
        body = f"(do {before} (let [__c_result {call}] {after} __c_result))"
        root_return = return_type
    output_lines.append(f"(defn main [{arguments}] (-> {root_return}) {body})")

    build_dir.mkdir(parents=True, exist_ok=True)
    generated_path = build_dir / "program.coil"
    generated_path.write_text("\n".join(output_lines) + "\n")
    command = [shutil.which("coil") or "coil", "build", str(generated_path), f"-O{optimization}", "-o", str(output)]
    for flag in link_flags:
        command += ["--link-flag", flag]
    process = subprocess.run(command, cwd=ROOT)
    if process.returncode:
        raise BuildError(f"Coil build failed with exit status {process.returncode}; generated source: {generated_path}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sources", nargs="+", type=pathlib.Path)
    parser.add_argument("-o", "--output", required=True, type=pathlib.Path)
    parser.add_argument("-O", "--optimization", choices=("0", "1", "2", "3"), default="3")
    parser.add_argument("--cflag", action="append", default=[])
    parser.add_argument("--link-flag", action="append", default=[])
    parser.add_argument("--build-dir", type=pathlib.Path,
                        help="retain generated Coil in this directory instead of using a temporary directory")
    args = parser.parse_args()
    sources = [source.resolve() for source in args.sources]
    missing = [source for source in sources if not source.is_file()]
    if missing:
        parser.error("missing source: " + ", ".join(str(source) for source in missing))
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        if args.build_dir:
            compile_program(sources, output, args.cflag, args.link_flag, args.optimization,
                            args.build_dir.resolve())
        else:
            (ROOT / "build").mkdir(exist_ok=True)
            with tempfile.TemporaryDirectory(prefix="c-build-", dir=ROOT / "build") as temporary:
                compile_program(sources, output, args.cflag, args.link_flag, args.optimization,
                                pathlib.Path(temporary))
    except BuildError as error:
        print(f"c-build: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
