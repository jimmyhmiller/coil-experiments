"""Conservative native-Coil to CoilRS renderer.

Every renderer returns None when a native shape cannot be reproduced exactly by
the structured reader. Callers then preserve that form with coil_item.
"""

from __future__ import annotations

from dataclasses import dataclass
import re


class NativeParseError(ValueError):
    pass


@dataclass
class Node:
    kind: str
    value: str | list["Node"]
    start: int
    end: int

    def atom(self) -> str | None:
        return self.value if self.kind == "atom" else None  # type: ignore[return-value]


DELIMS = set("()[]'`~")


def parse_forms(source: str) -> list[Node]:
    parser = NativeParser(source)
    forms: list[Node] = []
    while True:
        parser.space()
        if parser.i >= len(source):
            return forms
        forms.append(parser.node())


class NativeParser:
    def __init__(self, source: str):
        self.source = source
        self.i = 0

    def space(self) -> None:
        while self.i < len(self.source):
            if self.source[self.i].isspace():
                self.i += 1
            elif self.source[self.i] == ";":
                end = self.source.find("\n", self.i + 1)
                self.i = len(self.source) if end < 0 else end + 1
            else:
                return

    def node(self) -> Node:
        self.space()
        if self.i >= len(self.source):
            raise NativeParseError("unexpected end of input")
        start = self.i
        ch = self.source[self.i]
        if ch in "([":
            close = ")" if ch == "(" else "]"
            kind = "list" if ch == "(" else "vector"
            self.i += 1
            values: list[Node] = []
            while True:
                self.space()
                if self.i >= len(self.source):
                    raise NativeParseError(f"unterminated {ch!r} at byte {start}")
                if self.source[self.i] == close:
                    self.i += 1
                    return Node(kind, values, start, self.i)
                values.append(self.node())
        if ch in "'`~":
            self.i += 1
            if ch == "~" and self.i < len(self.source) and self.source[self.i] == "@":
                self.i += 1
            self.node()
            return Node("unsupported", self.source[start:self.i], start, self.i)
        if ch == '"' or (ch == "c" and self.i + 1 < len(self.source) and self.source[self.i + 1] == '"'):
            if ch == "c":
                self.i += 1
            self.i += 1
            escaped = False
            while self.i < len(self.source):
                current = self.source[self.i]
                self.i += 1
                if escaped:
                    escaped = False
                elif current == "\\":
                    escaped = True
                elif current == '"':
                    return Node("atom", self.source[start:self.i], start, self.i)
            raise NativeParseError(f"unterminated string at byte {start}")
        if self.source.startswith("#\\", self.i):
            self.i += 2
            if self.i < len(self.source):
                self.i += 1
            while self.i < len(self.source) and not self.source[self.i].isspace() and self.source[self.i] not in "()[];":
                self.i += 1
            return Node("atom", self.source[start:self.i], start, self.i)
        if ch == "\\":
            # Legacy Coil character literal (\x, \newline, and even \().
            # Consume it correctly but keep its containing form on the exact
            # fallback path; canonical modern characters use #\.
            self.i += 1
            if self.i < len(self.source):
                self.i += 1
            while self.i < len(self.source) and not self.source[self.i].isspace() and self.source[self.i] not in "()[];":
                self.i += 1
            return Node("unsupported", self.source[start:self.i], start, self.i)
        self.i += 1
        while self.i < len(self.source):
            current = self.source[self.i]
            if current.isspace() or current in "()[];":
                break
            self.i += 1
        return Node("atom", self.source[start:self.i], start, self.i)


def children(node: Node) -> list[Node] | None:
    return node.value if node.kind in ("list", "vector") else None  # type: ignore[return-value]


def head(node: Node) -> str | None:
    values = children(node)
    return values[0].atom() if values else None


SIMPLE_IDENT = re.compile(r"[@A-Za-z_][A-Za-z0-9_?!-]*$")
RESERVED = {
    "module", "use", "pub", "export", "struct", "enum", "const", "fn", "trait",
    "impl", "for", "extern", "cimport", "export_c", "meta", "checker", "transform",
    "transform_once", "coil", "coil_item", "coil_expr", "let", "mut", "if", "else",
    "match", "cond", "case", "comptime", "try", "block", "return_from", "loop",
    "while", "when", "unless", "break", "continue", "in", "as", "with", "except",
}


def ident(symbol: str) -> str:
    if symbol.startswith(":") or symbol.startswith('"') or symbol.startswith("c\""):
        return symbol
    if "/" in symbol:
        prefix, leaf = symbol.rsplit("/", 1)
        return "::".join(prefix.split(".")) + "::" + leaf
    if (SIMPLE_IDENT.fullmatch(symbol) or "::" in symbol) and symbol not in RESERVED:
        return symbol
    return "`" + symbol.replace("`", "") + "`"


def module_ident(symbol: str) -> str:
    return "::".join(ident(part) for part in symbol.split("."))


def type_rs(node: Node) -> str | None:
    atom = node.atom()
    if atom is not None:
        return ident(atom)
    values = children(node)
    if not values or values[0].atom() is None:
        return None
    rendered = [type_rs(value) for value in values[1:]]
    if any(value is None for value in rendered):
        return None
    return f"{ident(values[0].atom() or '')}<" + ", ".join(rendered) + ">"


INFIX = {"+", "-", "*", "/", "%", "!=", "<", "<=", ">", ">=", "&", "|", "^", "<<", ">>"}


def expression(node: Node) -> str | None:
    atom = node.atom()
    if atom is not None:
        if atom.startswith("#\\"):
            value = atom[2:]
            named = {"newline": "\\n", "return": "\\r", "tab": "\\t", "null": "\\0"}
            return "'" + named.get(value, value) + "'"
        if (
            atom.startswith(('"', 'c"', ":"))
            or atom in ("true", "false")
            or re.fullmatch(r"[-+]?(?:0[xX][0-9A-Fa-f_]+|0[bB][01_]+|0[oO][0-7_]+|[0-9][0-9A-Za-z_.]*)", atom)
        ):
            return atom
        return ident(atom)
    if node.kind == "vector":
        rendered = [expression(value) for value in children(node) or []]
        if any(value is None for value in rendered):
            return None
        return "[" + ", ".join(rendered) + "]"
    values = children(node)
    if not values:
        return None
    form = values[0].atom()
    if form is None:
        return None
    args = values[1:]
    if form == "=" and len(args) == 2:
        a, b = expression(args[0]), expression(args[1])
        return None if a is None or b is None else f"({a} == {b})"
    if form in INFIX and len(args) == 2:
        a, b = expression(args[0]), expression(args[1])
        return None if a is None or b is None else f"({a} {form} {b})"
    if form == "and" and len(args) == 2:
        a, b = expression(args[0]), expression(args[1])
        return None if a is None or b is None else f"({a} && {b})"
    if form == "or" and len(args) == 2:
        a, b = expression(args[0]), expression(args[1])
        return None if a is None or b is None else f"({a} || {b})"
    if form == "not" and len(args) == 1:
        value = expression(args[0])
        return None if value is None else f"!{value}"
    if form == "if" and len(args) == 3:
        condition = expression(args[0])
        yes = block_from_expression(args[1])
        no = block_from_expression(args[2])
        return None if None in (condition, yes, no) else f"if {condition} {yes} else {no}"
    if form == "do":
        return block(args)
    if form == "let" and len(args) >= 2 and args[0].kind == "vector":
        bindings = children(args[0]) or []
        if len(bindings) % 2:
            return None
        lines: list[str] = []
        for i in range(0, len(bindings), 2):
            binding = bindings[i]
            value = expression(bindings[i + 1])
            if value is None:
                return None
            bvalues = children(binding)
            if bvalues and len(bvalues) == 2 and bvalues[0].atom() == "mut" and bvalues[1].atom():
                lines.append(f"let mut {ident(bvalues[1].atom() or '')} = {value};")
            elif binding.atom() is not None:
                lines.append(f"let {ident(binding.atom() or '')} = {value};")
            else:
                return None
        body_values = [expression(value) for value in args[1:]]
        if any(value is None for value in body_values):
            return None
        for i, value in enumerate(body_values):
            lines.append((value or "") + (";" if i + 1 < len(body_values) else ""))
        return "{ " + " ".join(lines) + " }"
    if form == "load" and len(args) == 1:
        value = expression(args[0])
        return None if value is None else f"*{value}"
    if form == "mut" and len(args) == 1:
        value = expression(args[0])
        return None if value is None else f"mut {value}"
    if form in ("store!", "set!") and len(args) == 2:
        place, value = expression(args[0]), expression(args[1])
        return None if place is None or value is None else f"{place} = {value}"
    if form.startswith(".") and len(args) == 1:
        value = expression(args[0])
        return None if value is None else f"{value}.{ident(form[1:])}"
    if form == "break":
        if not args:
            return "break"
        value = expression(args[0]) if len(args) == 1 else None
        return None if value is None else f"break {value}"
    if form == "continue" and not args:
        return "continue"
    if form in ("loop", "while", "when", "unless"):
        if form == "loop":
            body = block(args)
            return None if body is None else f"loop {body}"
        if not args:
            return None
        condition = expression(args[0])
        body = block(args[1:])
        return None if condition is None or body is None else f"{form} {condition} {body}"
    if form == "for" and len(args) >= 2 and args[0].kind == "vector":
        binding = children(args[0]) or []
        if len(binding) != 3 or binding[0].atom() is None:
            return None
        start, end = expression(binding[1]), expression(binding[2])
        body = block(args[1:])
        if start is None or end is None or body is None:
            return None
        return f"for {ident(binding[0].atom() or '')} in {start}..{end} {body}"
    if form == "comptime" and len(args) == 1:
        body = block_from_expression(args[0])
        return None if body is None else f"comptime {body}"
    if form == "return-from" and len(args) == 2 and args[0].atom():
        value = expression(args[1])
        return None if value is None else f"return_from {args[0].atom()}, {value}"
    if form == "match" and len(args) >= 2:
        matched = expression(args[0])
        if matched is None:
            return None
        clauses: list[str] = []
        for clause in args[1:]:
            clause_values = children(clause)
            if not clause_values or len(clause_values) < 3 or clause_values[0].atom() is None:
                return None
            pattern_values = children(clause_values[1])
            if pattern_values is None or not all(value.atom() for value in pattern_values):
                return None
            result = (
                block(clause_values[2:])
                if len(clause_values) > 3
                else expression(clause_values[2])
            )
            if result is None:
                return None
            pattern = ident(clause_values[0].atom() or "")
            if pattern_values:
                pattern += "[" + ", ".join(ident(value.atom() or "") for value in pattern_values) + "]"
            clauses.append(f"{pattern} => {result}")
        return f"match {matched} {{ " + ", ".join(clauses) + " }"
    if form == "cond" and len(args) >= 1:
        clauses: list[str] = []
        pair_end = len(args) if len(args) % 2 == 0 else len(args) - 1
        for i in range(0, pair_end, 2):
            test = args[i].atom()
            rendered_test = "else" if test == ":else" else expression(args[i])
            result = expression(args[i + 1])
            if rendered_test is None or result is None:
                return None
            clauses.append(f"{rendered_test} => {result}")
        if pair_end != len(args):
            default = expression(args[-1])
            if default is None:
                return None
            clauses.append(f"else => {default}")
        return "cond { " + ", ".join(clauses) + " }"
    if form == "case" and len(args) >= 2:
        matched = expression(args[0])
        if matched is None:
            return None
        rest = args[1:]
        clauses: list[str] = []
        for i in range(0, len(rest) - 1, 2):
            key, result = expression(rest[i]), expression(rest[i + 1])
            if key is None or result is None:
                return None
            clauses.append(f"{key} => {result}")
        default = expression(rest[-1])
        if default is None:
            return None
        clauses.append(f"else => {default}")
        return f"case {matched} {{ " + ", ".join(clauses) + " }"
    # Named struct/sum construction.
    if form and form[0].isupper() and len(args) % 2 == 0 and all(
        args[i].atom() and (args[i].atom() or "").startswith(":") for i in range(0, len(args), 2)
    ):
        fields: list[str] = []
        for i in range(0, len(args), 2):
            value = expression(args[i + 1])
            if value is None:
                return None
            fields.append(f"{ident((args[i].atom() or '')[1:])}: {value}")
        return f"{ident(form)} {{ " + ", ".join(fields) + " }"
    # Ordinary or explicitly generic call.
    call_args = args
    generic = ""
    if call_args and call_args[0].kind == "vector":
        types = [type_rs(value) for value in children(call_args[0]) or []]
        if any(value is None for value in types):
            return None
        generic = "::<" + ", ".join(types) + ">"
        call_args = call_args[1:]
    rendered = [expression(value) for value in call_args]
    if any(value is None for value in rendered):
        return None
    return f"{ident(form)}{generic}(" + ", ".join(rendered) + ")"


def block(values: list[Node]) -> str | None:
    rendered = [expression(value) for value in values]
    if any(value is None for value in rendered):
        return None
    if not rendered:
        return "{ 0 }"
    return "{ " + " ".join((value or "") + (";" if i + 1 < len(rendered) else "") for i, value in enumerate(rendered)) + " }"


def block_from_expression(node: Node) -> str | None:
    if head(node) == "do":
        return block((children(node) or [])[1:])
    value = expression(node)
    if value is None:
        return None
    if value.startswith("{") and value.endswith("}"):
        return value
    return "{ " + value + " }"


def params_rs(node: Node) -> str | None:
    if node.kind != "vector":
        return None
    out: list[str] = []
    for param in children(node) or []:
        pair = children(param)
        if not pair or len(pair) != 2 or pair[0].atom() is None:
            return None
        typ = type_rs(pair[1])
        if typ is None:
            return None
        out.append(f"{ident(pair[0].atom() or '')}: {typ}")
    return ", ".join(out)


def generics_rs(node: Node) -> str | None:
    if node.kind != "vector":
        return None
    out: list[str] = []
    for parameter in children(node) or []:
        atom = parameter.atom()
        if atom is not None:
            out.append(ident(atom))
            continue
        values = children(parameter)
        if not values or values[0].atom() is None:
            return None
        bounds = [value.atom() for value in values[1:]]
        if any(bound is None for bound in bounds):
            return None
        out.append(f"{ident(values[0].atom() or '')}: " + " + ".join(ident(bound or "") for bound in bounds))
    return "<" + ", ".join(out) + ">" if out else ""


def function_rs(node: Node, method: bool = False) -> str | None:
    values = children(node)
    if not values or (not method and values[0].atom() != "defn"):
        return None
    offset = 0 if method else 1
    if len(values) < offset + 4 or values[offset].atom() is None:
        return None
    name = ident(values[offset].atom() or "")
    cursor = offset + 1
    generic = ""
    # A generic vector is followed by the parameter vector.
    if cursor + 1 < len(values) and values[cursor].kind == "vector" and values[cursor + 1].kind == "vector":
        generic_value = generics_rs(values[cursor])
        if generic_value is None:
            return None
        generic = generic_value
        cursor += 1
    params = params_rs(values[cursor]) if cursor < len(values) else None
    cursor += 1
    returns = children(values[cursor]) if cursor < len(values) else None
    if params is None or not returns or len(returns) != 2 or returns[0].atom() != "->":
        return None
    ret = type_rs(returns[1])
    cursor += 1
    if ret is None or cursor >= len(values):
        return None
    bodies = values[cursor:]
    body = block_from_expression(bodies[0]) if len(bodies) == 1 else block(bodies)
    if body is None:
        return None
    return f"fn {name}{generic}({params}) -> {ret} {body}"


def top_level(node: Node) -> str | None:
    values = children(node)
    if not values or values[0].atom() is None:
        return None
    form = values[0].atom() or ""
    if form == "module" and len(values) == 2 and values[1].atom():
        return f"module {module_ident(values[1].atom() or '')};"
    if form == "export" and all(value.atom() for value in values[1:]):
        return "export { " + ", ".join(ident(value.atom() or "") for value in values[1:]) + " };"
    if form == "import" and len(values) >= 2 and values[1].atom() and (values[1].atom() or "").startswith('"'):
        clauses: list[str] = []
        i = 2
        while i < len(values):
            key = values[i].atom()
            if key not in (":as", ":use", ":exclude", ":rename", ":reexport"):
                return None
            if key == ":reexport":
                clauses.append("reexport: true")
                i += 1
                continue
            if i + 1 >= len(values):
                return None
            value = values[i + 1]
            if key == ":as" and value.atom():
                rendered = ident(value.atom() or "")
            elif key == ":use" and value.atom() == "*":
                rendered = "*"
            elif key in (":use", ":exclude") and value.kind == "vector" and all(x.atom() for x in children(value) or []):
                rendered = "[" + ", ".join(ident(x.atom() or "") for x in children(value) or []) + "]"
            elif key == ":rename" and value.kind == "vector":
                pairs: list[str] = []
                for pair in children(value) or []:
                    pair_values = children(pair)
                    if not pair_values or len(pair_values) != 2 or not all(x.atom() for x in pair_values):
                        return None
                    pairs.append("[" + ", ".join(ident(x.atom() or "") for x in pair_values) + "]")
                rendered = "[" + ", ".join(pairs) + "]"
            else:
                return None
            clauses.append(key[1:] + ": " + rendered)
            i += 2
        module = values[1].atom() or '""'
        return f"use {module}" + (" with { " + ", ".join(clauses) + " }" if clauses else "") + ";"
    if form in ("defstruct", "defsum") and len(values) >= 3 and values[1].atom():
        name = ident(values[1].atom() or "")
        cursor = 2
        generic = ""
        if values[cursor].kind == "vector" and form == "defsum" or (
            values[cursor].kind == "vector" and any((children(x) or [Node('', '', 0, 0)])[0].atom() is None for x in children(values[cursor]) or [])
        ):
            # Ambiguous with a struct's field vector; only treat an all-atom vector as generics.
            if all(x.atom() for x in children(values[cursor]) or []):
                rendered_generic = generics_rs(values[cursor])
                if rendered_generic is None:
                    return None
                generic = rendered_generic
                cursor += 1
        if form == "defstruct":
            if cursor >= len(values) or values[cursor].kind != "vector":
                return None
            fields: list[str] = []
            for field in children(values[cursor]) or []:
                pair = children(field)
                if not pair or len(pair) != 2 or pair[0].atom() is None:
                    return None
                typ = type_rs(pair[1])
                if typ is None:
                    return None
                fields.append(f"{ident(pair[0].atom() or '')}: {typ}")
            return f"struct {name}{generic} {{ " + ", ".join(fields) + " }"
        variants: list[str] = []
        for variant in values[cursor:]:
            variant_values = children(variant)
            if not variant_values or variant_values[0].atom() is None:
                return None
            fields: list[str] = []
            if len(variant_values) == 2:
                if variant_values[1].kind != "vector":
                    return None
                for field in children(variant_values[1]) or []:
                    pair = children(field)
                    if not pair or len(pair) != 2 or pair[0].atom() is None:
                        return None
                    typ = type_rs(pair[1])
                    if typ is None:
                        return None
                    fields.append(f"{ident(pair[0].atom() or '')}: {typ}")
            variants.append(ident(variant_values[0].atom() or "") + (" { " + ", ".join(fields) + " }" if fields else ""))
        return f"enum {name}{generic} {{ " + ", ".join(variants) + " }"
    if form == "const" and len(values) in (3, 4) and values[1].atom():
        if len(values) == 3:
            typ, value_node = None, values[2]
        else:
            typ, value_node = type_rs(values[2]), values[3]
            if typ is None:
                return None
        value = expression(value_node)
        return None if value is None else f"const {ident(values[1].atom() or '')}{': ' + typ if typ else ''} = {value};"
    if form == "defn":
        return function_rs(node)
    if form == "extern" and len(values) >= 6 and values[1].atom() and values[2].atom() == ":cc" and values[3].atom():
        params = values[4]
        returns = children(values[5])
        if params.kind != "vector" or not returns or len(returns) != 2 or returns[0].atom() != "->":
            return None
        rendered_params: list[str] = []
        for i, param in enumerate(children(params) or []):
            if param.atom() == "...":
                rendered_params.append("...")
            else:
                typ = type_rs(param)
                if typ is None:
                    return None
                rendered_params.append(f"arg{i}: {typ}")
        ret = type_rs(returns[1])
        if ret is None:
            return None
        return f"extern \"{values[3].atom()}\" {{ fn {ident(values[1].atom() or '')}(" + ", ".join(rendered_params) + f") -> {ret}; }}"
    return None


def node_key(node: Node):
    if node.kind in ("atom", "unsupported"):
        return node.kind, node.value
    return node.kind, tuple(node_key(value) for value in children(node) or [])


def exact_structured_render(original: Node, rendered: str | None) -> str | None:
    if rendered is None:
        return None
    # Import locally to keep the two parsers independently usable.
    from structured import ParseError, parse as parse_structured

    try:
        reconstructed = parse_forms(parse_structured(rendered))
    except (ParseError, NativeParseError):
        return None
    if len(reconstructed) != 1 or node_key(original) != node_key(reconstructed[0]):
        return None
    return rendered


def render_program(source: str) -> str:
    forms = parse_forms(source)
    rendered: list[str] = []
    cursor = 0
    for form in forms:
        trivia = source[cursor:form.start]
        # Preserve comments as ordinary Rust-style comments when a form is structured.
        converted = exact_structured_render(form, top_level(form))
        if converted is None:
            raw = source[cursor:form.end].strip("\n")
            rendered.append("coil_item {\n" + raw + "\n}")
        else:
            comment_lines: list[str] = []
            for line in trivia.splitlines():
                stripped = line.lstrip()
                if stripped.startswith(";;"):
                    comment_lines.append("///" + stripped[2:])
                elif stripped.startswith(";"):
                    comment_lines.append("//" + stripped[1:])
            if comment_lines:
                rendered.extend(comment_lines)
            rendered.append(converted)
        cursor = form.end
    trailing = source[cursor:].strip()
    if trailing:
        rendered.append("coil_item {\n" + trailing + "\n}")
    return "\n\n".join(rendered) + "\n"
