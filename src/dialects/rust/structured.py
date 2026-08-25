"""Structured CoilRS lexer and parser.

This module intentionally emits ordinary Coil text.  It covers the ergonomic
core; unknown declarations remain representable with coil_item/coil_expr.
"""

from __future__ import annotations

from dataclasses import dataclass


class ParseError(ValueError):
    pass


@dataclass(frozen=True)
class Token:
    text: str
    at: int
    quoted: bool = False


MULTI = (
    "<<=", ">>=", "...", "::", "->", "=>", "==", "!=", "<=", ">=", "&&", "||",
    "+=", "-=", "*=", "/=", "%=", "&=", "|=", "^=", "<<", ">>", "..",
)
PUNCT = set("#{}()[];,.-+*/%^&|!<>=")


def _escape_close(source: str, opening: int) -> int:
    depth = 1
    i = opening + 1
    mode = "normal"
    escaped = False
    while i < len(source):
        ch = source[i]
        if mode == "comment":
            if ch == "\n":
                mode = "normal"
            i += 1
            continue
        if mode == "string":
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                mode = "normal"
            i += 1
            continue
        if source.startswith(";;", i):
            mode = "comment"
            i += 2
            continue
        if ch == '"':
            mode = "string"
            i += 1
            continue
        if source.startswith("#\\", i):
            # Skip one character literal payload; named characters continue to
            # the next native delimiter and cannot contain a brace.
            i += 2
            if i < len(source):
                i += 1
            while i < len(source) and not source[i].isspace() and source[i] not in "()[]{}\";":
                i += 1
            continue
        if ch == "\\":
            # Legacy native character literal, including \{ and \}.
            i += 1
            if i < len(source):
                i += 1
            while i < len(source) and not source[i].isspace() and source[i] not in "()[]{}\";":
                i += 1
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    raise ParseError(f"unterminated native escape at byte {opening}")


def lex(source: str) -> list[Token]:
    out: list[Token] = []
    i = 0
    n = len(source)
    while i < n:
        ch = source[i]
        if ch.isspace():
            i += 1
            continue
        if source.startswith("///", i):
            end = source.find("\n", i + 3)
            if end < 0:
                end = n
            out.append(Token("///" + source[i + 3 : end], i))
            i = end
            continue
        if source.startswith("//", i):
            end = source.find("\n", i + 2)
            i = n if end < 0 else end + 1
            continue
        if source.startswith("/*", i):
            depth = 1
            i += 2
            while depth and i < n:
                if source.startswith("/*", i):
                    depth += 1
                    i += 2
                elif source.startswith("*/", i):
                    depth -= 1
                    i += 2
                else:
                    i += 1
            if depth:
                raise ParseError("unterminated block comment")
            continue
        start = i
        escape_word = next(
            (
                word
                for word in ("coil_item", "coil_expr", "coil")
                if source.startswith(word, i)
                and (i + len(word) == n or not (source[i + len(word)].isalnum() or source[i + len(word)] == "_"))
            ),
            None,
        )
        if escape_word is not None:
            probe = i + len(escape_word)
            while probe < n and source[probe].isspace():
                probe += 1
            if probe < n and source[probe] == "{":
                close = _escape_close(source, probe)
                out.append(Token(escape_word, i))
                out.append(Token("{", probe))
                out.append(Token("<native>", probe + 1))
                out.append(Token("}", close))
                i = close + 1
                continue
        prefix = ""
        if ch == "c" and i + 1 < n and source[i + 1] == '"':
            prefix = "c"
            i += 1
            ch = '"'
        if ch == '"':
            i += 1
            escaped = False
            while i < n:
                current = source[i]
                i += 1
                if escaped:
                    escaped = False
                elif current == "\\":
                    escaped = True
                elif current == '"':
                    break
            else:
                raise ParseError(f"unterminated string at byte {start}")
            out.append(Token(prefix + source[start + len(prefix):i], start))
            continue
        if ch == "'":
            i += 1
            escaped = False
            while i < n:
                current = source[i]
                i += 1
                if escaped:
                    escaped = False
                elif current == "\\":
                    escaped = True
                elif current == "'":
                    break
            else:
                raise ParseError(f"unterminated character at byte {start}")
            out.append(Token(source[start:i], start))
            continue
        if ch == "`":
            end = source.find("`", i + 1)
            if end < 0:
                raise ParseError(f"unterminated backtick identifier at byte {start}")
            out.append(Token(source[i + 1:end], start, True))
            i = end + 1
            continue
        matched = next((op for op in MULTI if source.startswith(op, i)), None)
        if matched is not None:
            out.append(Token(matched, i))
            i += len(matched)
            continue
        if ch in PUNCT:
            out.append(Token(ch, i))
            i += 1
            continue
        if ch.isdigit():
            i += 1
            while i < n and (source[i].isalnum() or source[i] in "_."):
                if source.startswith("..", i):
                    break
                i += 1
            out.append(Token(source[start:i], start))
            continue
        if ch.isalpha() or ch == "_" or ch == "@":
            i += 1
            while i < n and (source[i].isalnum() or source[i] in "_-?!"):
                i += 1
            if source.startswith("...", i):
                i += 3
            out.append(Token(source[start:i], start))
            continue
        if ch == ":":
            if i + 1 >= n or source[i + 1].isspace():
                out.append(Token(":", i))
                i += 1
                continue
            i += 1
            while i < n and (source[i].isalnum() or source[i] in "_-/?!"):
                i += 1
            out.append(Token(source[start:i], start))
            continue
        raise ParseError(f"unexpected character {ch!r} at byte {i}")
    out.append(Token("<eof>", n))
    return out


PRECEDENCE = {
    "||": 1,
    "&&": 2,
    "|": 3,
    "^": 4,
    "&": 5,
    "==": 6,
    "!=": 6,
    "<": 7,
    "<=": 7,
    ">": 7,
    ">=": 7,
    "<<": 8,
    ">>": 8,
    "+": 9,
    "-": 9,
    "*": 10,
    "/": 10,
    "%": 10,
}
LOWER_OP = {"==": "=", "&&": "and", "||": "or"}


class Parser:
    def __init__(self, source: str):
        self.source = source
        self.tokens = lex(source)
        self.i = 0

    def peek(self, text: str | None = None) -> Token | bool:
        token = self.tokens[self.i]
        return token if text is None else token.text == text and not token.quoted

    def take(self, text: str | None = None) -> Token:
        token = self.tokens[self.i]
        if text is not None and token.text != text:
            raise ParseError(f"expected {text!r} at byte {token.at}, found {token.text!r}")
        self.i += 1
        return token

    def maybe(self, text: str) -> bool:
        if self.peek(text):
            self.i += 1
            return True
        return False

    def name(self) -> str:
        first = self.take().text
        if first in PUNCT or first == "<eof>":
            raise ParseError(f"expected identifier, found {first!r}")
        parts = [first]
        while self.maybe("::"):
            parts.append(self.take().text)
        return self.qualify(parts)

    @staticmethod
    def qualify(parts: list[str]) -> str:
        if len(parts) == 1:
            return parts[0]
        if parts[0] and parts[0][0].isupper():
            return "::".join(parts)
        return ".".join(parts[:-1]) + "/" + parts[-1]

    def module_name(self) -> str:
        parts = [self.take().text]
        while self.maybe("::"):
            parts.append(self.take().text)
        return ".".join(parts)

    def type(self) -> str:
        name = self.name()
        if not self.maybe("<"):
            return name
        args: list[str] = []
        if not self.peek(">"):
            while True:
                if self.peek("["):
                    self.take("[")
                    values: list[str] = []
                    if not self.peek("]"):
                        while True:
                            values.append(self.type())
                            if not self.maybe(","):
                                break
                    self.take("]")
                    args.append("[" + " ".join(values) + "]")
                elif self.peek().text[0].isdigit():
                    args.append(self.take().text)
                else:
                    args.append(self.type())
                if not self.maybe(","):
                    break
        self.type_close()
        return f"({name} {' '.join(args)})"

    def type_close(self) -> None:
        if self.peek(">>"):
            token = self.peek()
            self.tokens[self.i] = Token(">", token.at + 1)  # type: ignore[union-attr]
            return
        self.take(">")

    def generics(self) -> str:
        if not self.maybe("<"):
            return ""
        params: list[str] = []
        while not self.peek(">"):
            name = self.take().text
            bounds: list[str] = []
            if self.maybe(":"):
                bounds.append(self.name())
                while self.maybe("+"):
                    bounds.append(self.name())
            params.append(name if not bounds else f"({name} {' '.join(bounds)})")
            if not self.maybe(","):
                break
        self.type_close()
        return "[" + " ".join(params) + "]"

    def program(self) -> str:
        forms: list[str] = []
        while not self.peek("<eof>"):
            docs: list[str] = []
            while self.peek().text.startswith("///"):
                docs.append(self.take().text[3:].lstrip())
            item_forms = self.item()
            if docs and item_forms:
                item_forms[0] = "\n".join(";; " + line for line in docs) + "\n" + item_forms[0]
            forms.extend(item_forms)
        return "\n".join(forms) + "\n"

    def item(self) -> list[str]:
        attributes: list[tuple[str, list[str]]] = []
        while self.peek("#"):
            attributes.append(self.attribute())
        if self.peek("module"):
            self.take()
            name = self.module_name()
            self.take(";")
            return [f"(module {name})"]
        if self.peek("use") or self.peek("pub"):
            return [self.use_item()]
        if self.peek("export"):
            self.take()
            self.take("{")
            names = self.comma_names("}")
            self.take(";")
            return [f"(export {' '.join(names)})"]
        if self.peek("struct"):
            form = self.struct_item()
            return [form, *self.derive_forms(attributes, form)]
        if self.peek("enum"):
            form = self.enum_item()
            return [form, *self.derive_forms(attributes, form)]
        if self.peek("const"):
            return [self.const_item()]
        if self.peek("fn"):
            return [self.fn_item(attributes)]
        if self.peek("trait"):
            return [self.trait_item()]
        if self.peek("impl"):
            return [self.impl_item()]
        if self.peek("extern"):
            return self.extern_items()
        if self.peek("cimport"):
            return [self.cimport_item()]
        if self.peek("export_c"):
            return [self.export_c_item()]
        if self.peek("meta"):
            self.take()
            return [f"(meta {self.block()})"]
        if self.peek("checker") or self.peek("transform") or self.peek("transform_once"):
            return [self.registration_item()]
        if self.peek("coil") or self.peek("coil_item"):
            return self.native_items()
        token = self.peek()
        raise ParseError(f"unsupported item {token.text!r} at byte {token.at}; use coil_item {{ ... }}")

    def attribute(self) -> tuple[str, list[str]]:
        self.take("#")
        self.take("[")
        name = self.name()
        args: list[str] = []
        if self.maybe("("):
            while not self.peek(")"):
                value = self.expr()
                if value and value[0].isupper() and " " not in value:
                    value = f"({value})"
                args.append(value)
                if not self.maybe(","):
                    break
            self.take(")")
        self.take("]")
        return name, args

    @staticmethod
    def declared_name(form: str) -> str:
        parts = form.lstrip("(").split()
        if len(parts) < 2:
            raise ParseError("could not determine declaration name for derive")
        return parts[1]

    def derive_forms(self, attributes: list[tuple[str, list[str]]], form: str) -> list[str]:
        out: list[str] = []
        target = self.declared_name(form)
        for name, args in attributes:
            if name != "derive":
                raise ParseError(f"attribute {name!r} is not valid on a type declaration")
            normalized = [arg[1:-1] if arg.startswith("(") and arg.endswith(")") and " " not in arg else arg for arg in args]
            out.append(f"(derive {' '.join(normalized)} {target})")
        return out

    def comma_names(self, close: str) -> list[str]:
        values: list[str] = []
        while not self.peek(close):
            values.append(self.name())
            if not self.maybe(","):
                break
        self.take(close)
        return values

    def use_item(self) -> str:
        reexport = False
        if self.maybe("pub"):
            reexport = True
        self.take("use")
        first = self.take().text
        if first.startswith('"'):
            module = first[1:-1]
            clauses = self.import_with_clauses() if self.maybe("with") else []
            self.take(";")
            return f'(import "{module}"{" " if clauses else ""}{" ".join(clauses)})'
        parts = [first]
        while self.peek("::") and self.tokens[self.i + 1].text not in ("*", "{"):
            self.take()
            parts.append(self.take().text)
        module = ".".join(parts)
        clauses: list[str] = []
        if self.maybe("::"):
            if self.maybe("*"):
                clauses.extend((":use", "*"))
            else:
                self.take("{")
                names: list[str] = []
                renames: list[str] = []
                while not self.peek("}"):
                    old = self.take().text
                    if self.maybe("as"):
                        renames.append(f"[{old} {self.take().text}]")
                    else:
                        names.append(old)
                    if not self.maybe(","):
                        break
                self.take("}")
                if names:
                    clauses.extend((":use", "[" + " ".join(names) + "]"))
                if renames:
                    clauses.extend((":rename", "[" + " ".join(renames) + "]"))
        if self.maybe("except"):
            self.take("{")
            excluded = self.comma_names("}")
            clauses.extend((":exclude", "[" + " ".join(excluded) + "]"))
        if self.maybe("as"):
            clauses.extend((":as", self.take().text))
        if reexport:
            clauses.append(":reexport")
        self.take(";")
        suffix = " " + " ".join(clauses) if clauses else ""
        return f'(import "{module}"{suffix})'

    def import_with_clauses(self) -> list[str]:
        self.take("{")
        clauses: list[str] = []
        while not self.peek("}"):
            key = self.take().text
            self.take(":")
            if key == "as":
                clauses.extend((":as", self.take().text))
            elif key == "use":
                if self.maybe("*"):
                    clauses.extend((":use", "*"))
                else:
                    self.take("[")
                    values = self.comma_names("]")
                    clauses.extend((":use", "[" + " ".join(values) + "]"))
            elif key == "exclude":
                self.take("[")
                values = self.comma_names("]")
                clauses.extend((":exclude", "[" + " ".join(values) + "]"))
            elif key == "rename":
                self.take("[")
                pairs: list[str] = []
                while not self.peek("]"):
                    self.take("[")
                    old = self.take().text
                    self.take(",")
                    new = self.take().text
                    self.take("]")
                    pairs.append(f"[{old} {new}]")
                    self.maybe(",")
                self.take("]")
                clauses.extend((":rename", "[" + " ".join(pairs) + "]"))
            elif key == "reexport":
                value = self.take().text
                if value != "true":
                    raise ParseError("import reexport must be true")
                clauses.append(":reexport")
            else:
                raise ParseError(f"unknown import clause {key!r}")
            self.maybe(",")
        self.take("}")
        return clauses

    def fields(self) -> list[tuple[str, str]]:
        self.take("{")
        fields: list[tuple[str, str]] = []
        while not self.peek("}"):
            name = self.take().text
            self.take(":")
            fields.append((name, self.type()))
            self.maybe(",")
        self.take("}")
        return fields

    def struct_item(self) -> str:
        self.take("struct")
        name = self.take().text
        generic = self.generics()
        fields = self.fields()
        head = f"(defstruct {name} {generic}" if generic else f"(defstruct {name}"
        return head + " [" + " ".join(f"({n} {t})" for n, t in fields) + "])"

    def enum_item(self) -> str:
        self.take("enum")
        name = self.take().text
        generic = self.generics()
        self.take("{")
        variants: list[str] = []
        while not self.peek("}"):
            variant = self.take().text
            fields = self.fields() if self.peek("{") else []
            variants.append(
                f"({variant} [" + " ".join(f"({n} {t})" for n, t in fields) + "])"
                if fields
                else f"({variant})"
            )
            self.maybe(",")
        self.take("}")
        head = f"(defsum {name} {generic}" if generic else f"(defsum {name}"
        return head + " " + " ".join(variants) + ")"

    def const_item(self) -> str:
        self.take("const")
        name = self.take().text
        typ = self.type() if self.maybe(":") else None
        self.take("=")
        value = self.expr()
        self.take(";")
        return f"(const {name}{' ' + typ if typ else ''} {value})"

    def fn_item(self, attributes: list[tuple[str, list[str]]] | None = None) -> str:
        self.take("fn")
        name, generic, params, ret = self.function_signature()
        body = self.block()
        attributes = attributes or []
        if any(attr == "test" for attr, _args in attributes):
            if params:
                raise ParseError("a #[test] function cannot have parameters")
            return f"(deftest {name} {body})"
        annotations: list[str] = []
        for attr, args in attributes:
            if attr == "test":
                continue
            key = attr if attr.startswith(":") else ":" + attr
            value = args[0] if len(args) == 1 else "(do " + " ".join(args) + ")"
            annotations.extend((key, value))
        prefix = f"(defn {name} {generic}" if generic else f"(defn {name}"
        if annotations:
            prefix += " " + " ".join(annotations)
        return f"{prefix} [{' '.join(params)}] (-> {ret}) {body})"

    def function_signature(self) -> tuple[str, str, list[str], str]:
        name = self.take().text
        generic = self.generics()
        self.take("(")
        params: list[str] = []
        while not self.peek(")"):
            pname = self.take().text
            packed_value = pname.endswith("...")
            if packed_value:
                pname = pname[:-3]
            self.take(":")
            params.append(f"({pname} {self.type()})" + (" ..." if packed_value else ""))
            if not self.maybe(","):
                break
        self.take(")")
        self.take("->")
        ret = self.type()
        return name, generic, params, ret

    def method(self, allow_body: bool) -> str:
        self.take("fn")
        name, generic, params, ret = self.function_signature()
        if generic:
            raise ParseError("method-level generic parameters require coil_item in version 1")
        if self.maybe(";"):
            if allow_body:
                raise ParseError(f"implementation method {name!r} requires a body")
            return f"({name} [{' '.join(params)}] (-> {ret}))"
        body = self.block()
        return f"({name} [{' '.join(params)}] (-> {ret}) {body})"

    def trait_item(self) -> str:
        self.take("trait")
        name = self.take().text
        params = self.generics()
        self.take("{")
        methods: list[str] = []
        while not self.peek("}"):
            methods.append(self.method(allow_body=False))
        self.take("}")
        return f"(deftrait {name} {params or '[]'} {' '.join(methods)})"

    def impl_item(self) -> str:
        self.take("impl")
        generic = self.generics()
        first = self.type()
        trait: str | None = None
        if self.maybe("for"):
            trait = first
            target = self.type()
        else:
            target = first
        self.take("{")
        methods: list[str] = []
        while not self.peek("}"):
            methods.append(self.method(allow_body=True))
        self.take("}")
        pieces = ["impl"]
        if generic:
            pieces.append(generic)
        if trait is not None:
            pieces.append(trait)
        pieces.append(target)
        pieces.extend(methods)
        return "(" + " ".join(pieces) + ")"

    def extern_items(self) -> list[str]:
        self.take("extern")
        convention = self.take().text
        if convention.startswith('"'):
            convention = convention[1:-1]
        self.take("{")
        forms: list[str] = []
        while not self.peek("}"):
            self.take("fn")
            name = self.take().text
            self.take("(")
            params: list[str] = []
            variadic = False
            while not self.peek(")"):
                if self.maybe("..."):
                    variadic = True
                    break
                _pname = self.take().text
                self.take(":")
                params.append(self.type())
                if not self.maybe(","):
                    break
            self.take(")")
            self.take("->")
            ret = self.type()
            self.take(";")
            if variadic:
                params.append("...")
            forms.append(f"(extern {name} :cc {convention} [{' '.join(params)}] (-> {ret}))")
        self.take("}")
        return forms

    def cimport_item(self) -> str:
        self.take("cimport")
        header = self.take().text
        self.take("{")
        names = self.comma_names("}")
        self.take(";")
        return f"(cimport {header} :use [{' '.join(names)}])"

    def export_c_item(self) -> str:
        self.take("export_c")
        self.take("{")
        values: list[str] = []
        while not self.peek("}"):
            name = self.take().text
            if self.maybe("as"):
                values.append(f"[{name} :as {self.take().text}]")
            else:
                values.append(name)
            if not self.maybe(","):
                break
        self.take("}")
        self.take(";")
        return f"(export-c {' '.join(values)})"

    def registration_item(self) -> str:
        kind = self.take().text.replace("_", "-")
        function = self.name()
        phase = ""
        if self.maybe("before_expand"):
            phase = " :phase before-expand"
        self.take(";")
        return f"({kind} {function}{phase})"

    def native_items(self) -> list[str]:
        self.take()
        open_token = self.take("{")
        start = open_token.at + 1
        depth = 1
        i = self.i
        while i < len(self.tokens):
            text = self.tokens[i].text
            if text == "<native>":
                i += 1
                continue
            if text == "{":
                depth += 1
            elif text == "}":
                depth -= 1
                if depth == 0:
                    end = self.tokens[i].at
                    self.i = i + 1
                    self.maybe(";")
                    # Item-position escapes splice their forms directly into
                    # the surrounding top-level sequence.
                    return [self.source[start:end]]
            i += 1
        raise ParseError("unterminated native item escape")

    def block(self) -> str:
        self.take("{")
        entries: list[tuple[str, str | tuple[str, str]]] = []
        while not self.peek("}"):
            if self.peek("let"):
                self.take()
                mutable = self.maybe("mut")
                name = self.take().text
                self.take("=")
                value = self.expr()
                self.take(";")
                binding = f"(mut {name})" if mutable else name
                entries.append(("let", (binding, value)))
            else:
                value = self.expr()
                semi = self.maybe(";")
                entries.append(("expr", value))
                if not semi and not self.peek("}"):
                    token = self.peek()
                    raise ParseError(f"expected ';' at byte {token.at}")
        self.take("}")
        def lower_from(index: int) -> list[str]:
            if index >= len(entries):
                return []
            kind, value = entries[index]
            if kind == "expr":
                return [str(value), *lower_from(index + 1)]
            bindings: list[str] = []
            cursor = index
            while cursor < len(entries) and entries[cursor][0] == "let":
                binding, init = entries[cursor][1]  # type: ignore[misc]
                bindings.extend((binding, init))
                cursor += 1
            tail_forms = lower_from(cursor)
            tail = " ".join(tail_forms) if tail_forms else "0"
            return [f"(let [{' '.join(bindings)}] {tail})"]

        accumulated = lower_from(0)
        if not accumulated:
            return "0"
        if len(accumulated) == 1:
            return accumulated[0]
        return "(do " + " ".join(accumulated) + ")"

    def expr(self, min_precedence: int = 0) -> str:
        left = self.prefix()
        while True:
            op = self.peek().text
            precedence = PRECEDENCE.get(op, -1)
            if precedence < min_precedence:
                break
            self.take()
            right = self.expr(precedence + 1)
            left = f"({LOWER_OP.get(op, op)} {left} {right})"
        if min_precedence == 0 and self.maybe("="):
            right = self.expr()
            if left.startswith("(."):
                return f"(set! {left} {right})"
            if left.startswith("(load ") and left.endswith(")"):
                return f"(store! {left[6:-1]} {right})"
            return f"(store! {left} {right})"
        if min_precedence == 0 and self.peek().text in (
            "+=", "-=", "*=", "/=", "%=", "&=", "|=", "^=", "<<=", ">>=",
        ):
            op = self.take().text[:-1]
            right = self.expr()
            place = left[6:-1] if left.startswith("(load ") and left.endswith(")") else left
            if (
                not place
                or place[0].isdigit()
                or any(character in place for character in "()[]{} \t\r\n\"'")
            ):
                raise ParseError(
                    "compound assignment requires a simple named place; "
                    "use explicit load/store! for a projected place"
                )
            return f"(store! {place} ({op} (load {place}) {right}))"
        return left

    def prefix(self) -> str:
        if self.peek("{"):
            return self.block()
        if self.maybe("mut"):
            return f"(mut {self.expr(11)})"
        if self.maybe("*"):
            return f"(load {self.expr(11)})"
        if self.maybe("!"):
            return f"(not {self.expr(11)})"
        if self.maybe("-"):
            return f"(- 0 {self.expr(11)})"
        if self.peek("if"):
            self.take()
            condition = self.expr()
            yes = self.block()
            self.take("else")
            no = self.block() if self.peek("{") else self.prefix()
            return f"(if {condition} {yes} {no})"
        if self.peek("match"):
            return self.match_expr()
        if self.peek("cond"):
            return self.cond_expr()
        if self.peek("case"):
            return self.case_expr()
        if self.peek("comptime"):
            self.take()
            return f"(comptime {self.block()})"
        if self.peek("try"):
            self.take()
            return f"(try {self.block()})"
        if self.peek("block"):
            self.take()
            label = self.take().text
            return f"(block {label} {self.block()})"
        if self.peek("return_from"):
            self.take()
            label = self.take().text
            self.take(",")
            return f"(return-from {label} {self.expr()})"
        if self.peek("loop"):
            self.take()
            return f"(loop {self.block()})"
        if self.peek("while"):
            self.take()
            condition = self.expr()
            return f"(while {condition} {self.block()})"
        if self.peek("for"):
            self.take()
            binding = self.take().text
            self.take("in")
            start = self.expr()
            self.take("..")
            end = self.expr()
            return f"(for [{binding} {start} {end}] {self.block()})"
        if self.peek("when") or self.peek("unless"):
            form = self.take().text
            condition = self.expr()
            return f"({form} {condition} {self.block()})"
        if self.peek("break"):
            self.take()
            return (
                "(break)"
                if self.peek(";") or self.peek("}") or self.peek(",")
                else f"(break {self.expr()})"
            )
        if self.peek("continue"):
            self.take()
            return "(continue)"
        if self.peek("coil_expr") or self.peek("coil"):
            items = self.native_items()
            return items[0].strip()
        if self.maybe("("):
            value = self.expr()
            self.take(")")
            return value
        if self.peek("["):
            self.take()
            values: list[str] = []
            while not self.peek("]"):
                values.append(self.expr())
                if not self.maybe(","):
                    break
            self.take("]")
            return "[" + " ".join(values) + "]"
        token = self.take().text
        if token.startswith("'"):
            content = token[1:-1]
            named = {"\\n": "newline", "\\r": "return", "\\t": "tab", "\\0": "null"}
            if content.startswith("\\u{") and content.endswith("}"):
                content = chr(int(content[3:-1], 16))
            token = "#\\" + named.get(content, content)
        parts = [token]
        while self.peek("::") and self.tokens[self.i + 1].text != "<":
            self.take("::")
            parts.append(self.take().text)
        left = self.qualify(parts)
        type_args = ""
        if self.maybe("::"):
            self.take("<")
            values: list[str] = []
            while not self.peek(">"):
                values.append(self.type())
                if not self.maybe(","):
                    break
            self.type_close()
            type_args = "[" + " ".join(values) + "]"
            if self.maybe("::"):
                left += "::" + self.take().text
        constructor_allowed = bool(parts[0]) and parts[0][0].isupper()
        while True:
            if self.maybe("("):
                args: list[str] = []
                while not self.peek(")"):
                    args.append(self.expr())
                    if not self.maybe(","):
                        break
                self.take(")")
                all_args = ([type_args] if type_args else []) + args
                left = f"({left}{' ' if all_args else ''}{' '.join(all_args)})"
                type_args = ""
                constructor_allowed = False
            elif self.maybe("."):
                field = self.take().text
                left = f"(.{field} {left})"
            elif self.maybe("["):
                index = self.expr()
                self.take("]")
                left = f"(get {left} {index})"
            elif self.peek("{") and constructor_allowed:
                self.take()
                fields: list[str] = []
                while not self.peek("}"):
                    field = self.take().text
                    self.take(":")
                    fields.extend((f":{field}", self.expr()))
                    self.maybe(",")
                self.take("}")
                left = f"({left} {' '.join(fields)})"
                constructor_allowed = False
            else:
                break
        return left

    def match_expr(self) -> str:
        self.take("match")
        value = self.expr()
        self.take("{")
        clauses: list[str] = []
        while not self.peek("}"):
            variant = self.take().text
            bindings: list[str] = []
            if self.maybe("["):
                while not self.peek("]"):
                    bindings.append(self.take().text)
                    if not self.maybe(","):
                        break
                self.take("]")
            self.take("=>")
            result = self.block() if self.peek("{") else self.expr()
            clauses.append(f"({variant} [{' '.join(bindings)}] {result})")
            self.maybe(",")
        self.take("}")
        return f"(match {value} {' '.join(clauses)})"

    def cond_expr(self) -> str:
        self.take("cond")
        self.take("{")
        clauses: list[str] = []
        while not self.peek("}"):
            test = ":else" if self.maybe("else") else self.expr()
            self.take("=>")
            result = self.block() if self.peek("{") else self.expr()
            clauses.extend((test, result))
            self.maybe(",")
        self.take("}")
        return f"(cond {' '.join(clauses)})"

    def case_expr(self) -> str:
        self.take("case")
        value = self.expr()
        self.take("{")
        clauses: list[str] = []
        default = "0"
        while not self.peek("}"):
            is_default = self.maybe("else")
            key = "" if is_default else self.expr()
            self.take("=>")
            result = self.block() if self.peek("{") else self.expr()
            if is_default:
                default = result
            else:
                clauses.extend((key, result))
            self.maybe(",")
        self.take("}")
        return f"(case {value} {' '.join(clauses)} {default})"


def parse(source: str) -> str:
    return Parser(source).program()
