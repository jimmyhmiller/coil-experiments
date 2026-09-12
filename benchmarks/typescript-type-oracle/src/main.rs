use std::{env, fs, path::PathBuf, process::Command};

use oxc_allocator::Allocator;
use oxc_ast::ast::{
    TSClassImplements, TSInterfaceBody, TSInterfaceHeritage, TSOptionalType, TSRestType,
    TSSignature, TSType, TSTypePredicateName, TSTypeQueryExprName,
};
use oxc_ast_visit::{walk, Visit};
use oxc_parser::Parser;
use oxc_span::{GetSpan, SourceType};

struct Case {
    name: &'static str,
    source: &'static str,
}

// Keep specimens isolated: the comparison is an ordered, post-order structural
// projection, so a failure names one syntax family instead of a large corpus.
const CASES: &[Case] = &[
    Case { name: "keywords", source: "type A=any;type B=bigint;type C=boolean;type D=intrinsic;type E=never;type F=null;type G=number;type H=object;type I=string;type J=symbol;type K=this;type L=undefined;type M=unknown;type N=void;" },
    Case { name: "reference-qualified-generics", source: "type T = A.B<C, D>;" },
    Case { name: "literals", source: "type T = 'x' | 1 | -2 | 3n | true | false;" },
    Case { name: "array-parenthesized", source: "type T = (A | B)[];" },
    Case { name: "conditional-infer", source: "type T<X> = X extends Array<infer U extends string> ? U : never;" },
    Case { name: "intersection-leading", source: "type T = & A & B;" },
    Case { name: "union-leading", source: "type T = | A | B;" },
    Case { name: "indexed-access", source: "type T = A[B];" },
    Case { name: "operators", source: "type A=keyof T;type B=readonly T[];type C=unique symbol;" },
    Case { name: "query", source: "type T = typeof A.B<C>;" },
    Case { name: "function", source: "type T = <X extends A = B>(this: C, x?: D, ...rest: E[]) => F<X>;" },
    Case { name: "constructor", source: "type T = abstract new <X>(x: X) => C<X>;" },
    Case { name: "tuple", source: "type T = [head: A, middle?: B, ...tail: C[]];" },
    Case { name: "mapped", source: "type T<K extends PropertyKey> = { readonly [P in K as `get${Capitalize<P & string>}`]?: A<P> };" },
    Case { name: "template", source: "type T = `a${A}b${B}c`;" },
    Case { name: "import", source: "type T = import('pkg', { with: { type: 'json' } }).A<B>;" },
    Case { name: "predicate", source: "type T = (x: unknown) => x is string;" },
    Case { name: "assertion-predicate", source: "type T = (x: unknown) => asserts x is string;" },
    Case { name: "type-literal-properties", source: "type T = { readonly plain?: A; 'quoted'; 0?: B; [key]?: C };" },
    Case { name: "type-literal-call", source: "type T = { <X>(x: X): X; new <Y>(y: Y): C<Y> };" },
    Case { name: "type-literal-methods", source: "type T = { get value(): A; set value(x: A); method?<X>(x: X): X };" },
    Case { name: "type-literal-index", source: "type T = { readonly [name: string]: number };" },
    Case { name: "delimiter-span-trivia", source: "type A0 = [A] ; type A1 = { x: A } ; type A2 = (A) ; type A3 = import('x').A<B> ; type A4 = `${A}` ; type A5 = A | B ; type A6 = A & B ; type A7 = A extends B ? C : D ; type A8 = { [K in A]: B } ; type A9 = keyof A ;" },
    Case { name: "mapped-variants", source: "type M0<K> = { [P in K]: A }; type M1<K> = { +readonly [P in K]-?: A }; type M2<K> = { -readonly [P in K]+?: A }; type M3<K> = { [P in K as Q] };" },
    Case { name: "import-variants", source: "type I0=import('x');type I1=typeof import('x');type I2=import('x').A;type I3=import('x')<A>;type I4=import('x',{with:{type:'json'}});" },
    Case { name: "predicate-variants", source: "type P0=(x:A)=>asserts x;type P1=()=>this is B;type P2=()=>asserts this;" },
    Case { name: "unnamed-tuple-wrappers", source: "type T=[A?,...B[]];" },
    Case { name: "computed-signatures", source: "type T={ [key]: A; 'quoted'?(): B; 0<C>(x:C):C; [method]<D>(x:D):D };" },
    Case { name: "callable-binding-patterns", source: "type F=({x:y=init,...rest}: A,[head,,...tail]: B)=>C;" },
    Case { name: "variable-type-context", source: "let x: A<B>; let y: { value: C | D };" },
    Case { name: "function-type-context", source: "function f<T extends A = B>(this: C, x?: D, ...rest: E[]): F<T> {}" },
    Case { name: "arrow-type-context", source: "const f = <T,>(x: T): T => x;" },
    Case { name: "class-type-context", source: "class C<T extends A> extends Base<T> implements I<T>, J { field?: A; method<U>(x: U): U { return x; } }" },
    Case { name: "interface-type-context", source: "interface I<T> extends A<T>, B { readonly value?: C<D>; method<U>(x: U): U }" },
    Case { name: "assertion-type-context", source: "const a = value as A<B>; const b = value satisfies C | D; const c = value!;" },
    Case { name: "call-new-type-context", source: "const a = fn<A, B>(x); const b = new C<D>(x); const c = fn<E>;" },
    Case { name: "angle-assertion-context", source: "const plain=<A>input; const nested=<A<B>>input;" },
];

struct Shape {
    nodes: Vec<&'static str>,
    spans: Vec<Option<(u32, u32)>>,
}

#[derive(Debug, PartialEq, Eq)]
struct Meta {
    operands: u32,
    immediate: u64,
}

struct FieldCheck {
    opcode: u16,
    expected: &'static [(u32, u64)],
}

fn field_checks(name: &str) -> &'static [FieldCheck] {
    match name {
        "keywords" => &[FieldCheck { opcode: 90, expected: &[(0, 0); 14] }],
        "reference-qualified-generics" => &[
            FieldCheck { opcode: 97, expected: &[(2, 0)] },
            FieldCheck { opcode: 89, expected: &[(0, 0), (0, 0), (0, 0), (2, 0)] },
        ],
        "literals" => &[
            FieldCheck { opcode: 91, expected: &[(0, 0); 6] },
            FieldCheck { opcode: 92, expected: &[(6, 0)] },
        ],
        "array-parenthesized" => &[
            FieldCheck { opcode: 92, expected: &[(2, 0)] },
            FieldCheck { opcode: 96, expected: &[(1, 0)] },
            FieldCheck { opcode: 94, expected: &[(1, 0)] },
        ],
        "conditional-infer" => &[
            FieldCheck { opcode: 105, expected: &[(4, 0)] },
            FieldCheck { opcode: 106, expected: &[(1, 0)] },
            FieldCheck { opcode: 111, expected: &[(0, 0), (1, 1)] },
        ],
        "intersection-leading" => &[FieldCheck { opcode: 93, expected: &[(2, 1)] }],
        "union-leading" => &[FieldCheck { opcode: 92, expected: &[(2, 1)] }],
        "indexed-access" => &[FieldCheck { opcode: 99, expected: &[(2, 0)] }],
        "operators" => &[FieldCheck { opcode: 100, expected: &[(1, 1), (1, 2), (1, 3)] }],
        "query" => &[FieldCheck { opcode: 101, expected: &[(2, 3)] }],
        "function" => &[
            FieldCheck { opcode: 102, expected: &[(5, 65)] },
            FieldCheck { opcode: 120, expected: &[(1, 20), (1, 17), (1, 18)] },
        ],
        "constructor" => &[FieldCheck { opcode: 103, expected: &[(3, 67)] }],
        "tuple" => &[
            FieldCheck { opcode: 95, expected: &[(3, 0)] },
            FieldCheck { opcode: 117, expected: &[(1, 0), (1, 1), (1, 0)] },
            FieldCheck { opcode: 118, expected: &[] },
            FieldCheck { opcode: 119, expected: &[(1, 0)] },
        ],
        "mapped" => &[
            FieldCheck { opcode: 107, expected: &[(3, 53)] },
            FieldCheck { opcode: 111, expected: &[(1, 1), (1, 1)] },
            FieldCheck { opcode: 108, expected: &[(3, 0)] },
        ],
        "template" => &[
            FieldCheck { opcode: 108, expected: &[(5, 0)] },
            FieldCheck { opcode: 123, expected: &[(0, 0), (0, 0), (0, 0)] },
        ],
        "import" => &[FieldCheck { opcode: 109, expected: &[(3, 7)] }],
        "predicate" => &[FieldCheck { opcode: 110, expected: &[(2, 2)] }],
        "assertion-predicate" => &[FieldCheck { opcode: 110, expected: &[(2, 3)] }],
        "type-literal-properties" => &[
            FieldCheck { opcode: 104, expected: &[(4, 0)] },
            FieldCheck { opcode: 112, expected: &[(1, 11), (0, 0), (1, 9), (2, 13)] },
        ],
        "type-literal-call" => &[
            FieldCheck { opcode: 104, expected: &[(2, 0)] },
            FieldCheck { opcode: 114, expected: &[(3, 65)] },
            FieldCheck { opcode: 115, expected: &[(3, 65)] },
        ],
        "type-literal-methods" => &[
            FieldCheck { opcode: 104, expected: &[(3, 0)] },
            FieldCheck { opcode: 113, expected: &[(1, 80), (1, 32), (3, 69)] },
        ],
        "type-literal-index" => &[
            FieldCheck { opcode: 104, expected: &[(1, 0)] },
            FieldCheck { opcode: 116, expected: &[(2, 2)] },
        ],
        "mapped-variants" => &[FieldCheck {
            opcode: 107,
            expected: &[(2, 32), (2, 46), (2, 43), (2, 16)],
        }],
        "import-variants" => &[
            FieldCheck { opcode: 109, expected: &[(0, 0), (0, 0), (1, 2), (1, 4), (1, 1)] },
            FieldCheck { opcode: 101, expected: &[(1, 1)] },
        ],
        "predicate-variants" => &[FieldCheck {
            opcode: 110,
            expected: &[(1, 1), (2, 6), (1, 5)],
        }],
        "unnamed-tuple-wrappers" => &[
            FieldCheck { opcode: 95, expected: &[(2, 0)] },
            FieldCheck { opcode: 118, expected: &[(1, 0)] },
            FieldCheck { opcode: 119, expected: &[(1, 0)] },
        ],
        "computed-signatures" => &[
            FieldCheck { opcode: 104, expected: &[(4, 0)] },
            FieldCheck { opcode: 112, expected: &[(2, 12)] },
            FieldCheck { opcode: 113, expected: &[(1, 68), (3, 65), (4, 73)] },
        ],
        "callable-binding-patterns" => &[
            FieldCheck { opcode: 102, expected: &[(3, 64)] },
            FieldCheck { opcode: 120, expected: &[(2, 24), (2, 24)] },
            FieldCheck { opcode: 128, expected: &[(2, 0)] },
            FieldCheck { opcode: 129, expected: &[(3, 0)] },
        ],
        "assertion-type-context" => &[FieldCheck {
            opcode: 122,
            expected: &[(2, 1), (2, 2)],
        }],
        "call-new-type-context" => &[FieldCheck {
            opcode: 52,
            expected: &[(2, 0), (2, 0), (2, 0)],
        }],
        "angle-assertion-context" => &[FieldCheck {
            opcode: 122,
            expected: &[(2, 3), (2, 3)],
        }],
        _ => &[],
    }
}

fn coil_metadata(output: &str, opcode: u16) -> Vec<Meta> {
    output.lines().filter_map(|line| {
        if !line.starts_with("meta ") { return None; }
        let mut found_opcode = None;
        let mut operands = None;
        let mut immediate = None;
        for field in line.split_whitespace() {
            if let Some(value) = field.strip_prefix("opcode=") {
                found_opcode = value.parse::<u16>().ok();
            } else if let Some(value) = field.strip_prefix("operands=") {
                operands = value.parse::<u32>().ok();
            } else if let Some(value) = field.strip_prefix("immediate=") {
                immediate = value.parse::<u64>().ok();
            }
        }
        (found_opcode == Some(opcode)).then(|| Meta {
            operands: operands.expect("metadata operand count"),
            immediate: immediate.expect("metadata immediate"),
        })
    }).collect()
}

impl Shape {
    fn new() -> Self { Self { nodes: Vec::new(), spans: Vec::new() } }

    fn push(&mut self, kind: &'static str, span: Option<(u32, u32)>) {
        self.nodes.push(kind);
        self.spans.push(span);
    }
}

impl<'a> Visit<'a> for Shape {
    fn visit_ts_type(&mut self, ty: &TSType<'a>) {
        // Oxc stores entity-name leaves as fields. Coil makes those leaves SSA
        // values when another operation (type arguments, a predicate, or an
        // import qualifier) must own them, so include that explicit lowering in
        // the normalized Oxc projection before visiting child types.
        match ty {
            TSType::TSTypeReference(node) if node.type_arguments.is_some() =>
                self.push("ts.type_reference", None),
            TSType::TSTypeQuery(node) if node.type_arguments.is_some() =>
                self.push("ts.type_reference", None),
            TSType::TSTypeQuery(node)
                if matches!(node.expr_name, TSTypeQueryExprName::TSImportType(_)) =>
                self.push("ts.import_type", None),
            TSType::TSImportType(node) if node.qualifier.is_some() =>
                self.push("ts.type_reference", None),
            TSType::TSTypePredicate(node) => self.push(
                match node.parameter_name {
                    TSTypePredicateName::Identifier(_) => "ts.type_reference",
                    TSTypePredicateName::This(_) => "ts.keyword_type",
                },
                None,
            ),
            _ => {}
        }
        walk::walk_ts_type(self, ty);
        let kind = match ty {
            TSType::TSAnyKeyword(_) | TSType::TSBigIntKeyword(_)
            | TSType::TSBooleanKeyword(_) | TSType::TSIntrinsicKeyword(_)
            | TSType::TSNeverKeyword(_) | TSType::TSNullKeyword(_)
            | TSType::TSNumberKeyword(_) | TSType::TSObjectKeyword(_)
            | TSType::TSStringKeyword(_) | TSType::TSSymbolKeyword(_)
            | TSType::TSThisType(_) | TSType::TSUndefinedKeyword(_)
            | TSType::TSUnknownKeyword(_) | TSType::TSVoidKeyword(_) => "ts.keyword_type",
            TSType::TSArrayType(_) => "ts.array_type",
            TSType::TSConditionalType(_) => "ts.conditional_type",
            TSType::TSConstructorType(_) => "ts.constructor_type",
            TSType::TSFunctionType(_) => "ts.function_type",
            TSType::TSImportType(_) => "ts.import_type",
            TSType::TSIndexedAccessType(_) => "ts.indexed_access_type",
            TSType::TSInferType(_) => "ts.infer_type",
            TSType::TSIntersectionType(_) => "ts.intersection_type",
            TSType::TSLiteralType(_) => "ts.literal_type",
            TSType::TSMappedType(_) => "ts.mapped_type",
            TSType::TSNamedTupleMember(_) => "ts.named_tuple_member",
            TSType::TSTemplateLiteralType(_) => "ts.template_literal_type",
            TSType::TSTupleType(_) => "ts.tuple_type",
            TSType::TSTypeLiteral(_) => "ts.type_literal",
            TSType::TSTypeOperatorType(_) => "ts.type_operator",
            TSType::TSTypePredicate(_) => "ts.type_predicate",
            TSType::TSTypeQuery(_) => "ts.type_query",
            TSType::TSTypeReference(_) => "ts.type_reference",
            TSType::TSUnionType(_) => "ts.union_type",
            TSType::TSParenthesizedType(_) => "ts.parenthesized_type",
            TSType::JSDocNullableType(_) | TSType::JSDocNonNullableType(_)
            | TSType::JSDocUnknownType(_) => panic!("JSDoc type in TypeScript specimen"),
        };
        let span = ty.span();
        self.push(kind, Some((span.start, span.end)));
    }

    fn visit_ts_optional_type(&mut self, ty: &TSOptionalType<'a>) {
        walk::walk_ts_optional_type(self, ty);
        let span = ty.span();
        self.push("ts.optional_type", Some((span.start, span.end)));
    }

    fn visit_ts_rest_type(&mut self, ty: &TSRestType<'a>) {
        walk::walk_ts_rest_type(self, ty);
        let span = ty.span();
        self.push("ts.rest_type", Some((span.start, span.end)));
    }

    fn visit_ts_signature(&mut self, signature: &TSSignature<'a>) {
        walk::walk_ts_signature(self, signature);
        let kind = match signature {
            TSSignature::TSIndexSignature(_) => "ts.index_signature",
            TSSignature::TSPropertySignature(_) => "ts.property_signature",
            TSSignature::TSCallSignatureDeclaration(_) => "ts.call_signature",
            TSSignature::TSConstructSignatureDeclaration(_) => "ts.construct_signature",
            TSSignature::TSMethodSignature(_) => "ts.method_signature",
        };
        let span = signature.span();
        self.push(kind, Some((span.start, span.end)));
    }

    fn visit_ts_interface_heritage(&mut self, heritage: &TSInterfaceHeritage<'a>) {
        if heritage.type_arguments.is_some() {
            self.push("ts.type_reference", None);
            walk::walk_ts_interface_heritage(self, heritage);
            let span = heritage.span();
            self.push("ts.type_reference", Some((span.start, span.end)));
        } else {
            walk::walk_ts_interface_heritage(self, heritage);
            let span = heritage.span();
            self.push("ts.type_reference", Some((span.start, span.end)));
        }
    }

    fn visit_ts_class_implements(&mut self, implementation: &TSClassImplements<'a>) {
        if implementation.type_arguments.is_some() {
            self.push("ts.type_reference", None);
        }
        walk::walk_ts_class_implements(self, implementation);
        let span = implementation.span();
        self.push("ts.type_reference", Some((span.start, span.end)));
    }

    fn visit_ts_interface_body(&mut self, body: &TSInterfaceBody<'a>) {
        walk::walk_ts_interface_body(self, body);
        let span = body.span();
        self.push("ts.type_literal", Some((span.start, span.end)));
    }
}

fn coil_shape(output: &str) -> Vec<&str> {
    const PRINCIPAL: &[&str] = &[
        "ts.keyword_type", "ts.literal_type", "ts.type_reference", "ts.union_type",
        "ts.intersection_type", "ts.array_type", "ts.tuple_type", "ts.parenthesized_type",
        "ts.indexed_access_type", "ts.type_operator", "ts.type_query", "ts.function_type",
        "ts.constructor_type", "ts.type_literal", "ts.conditional_type", "ts.infer_type",
        "ts.mapped_type", "ts.template_literal_type", "ts.import_type", "ts.type_predicate",
        "ts.property_signature", "ts.method_signature", "ts.call_signature",
        "ts.construct_signature", "ts.index_signature", "ts.named_tuple_member",
        "ts.optional_type", "ts.rest_type",
    ];
    output.lines().filter_map(|line| {
        let op = line.trim().split_once(" = ").map_or_else(
            || line.trim().split_whitespace().next(),
            |(_, rhs)| rhs.split_whitespace().next(),
        )?;
        PRINCIPAL.contains(&op).then_some(op)
    }).collect()
}

fn coil_spans(output: &str) -> Vec<(u32, u32)> {
    let kinds = coil_shape(output);
    output.lines().filter_map(|line| {
        let trimmed = line.trim();
        let op = trimmed.split_once(" = ").map_or_else(
            || trimmed.split_whitespace().next(),
            |(_, rhs)| rhs.split_whitespace().next(),
        )?;
        if !kinds.iter().any(|kind| *kind == op) { return None; }
        let location = trimmed.rsplit_once("loc(")?.1.strip_suffix(')')?;
        let (start, end) = location.split_once(':')?;
        Some((start.parse().ok()?, end.parse().ok()?))
    }).collect()
}

fn main() {
    let checker = PathBuf::from(env::args_os().nth(1)
        .expect("usage: typescript-type-oracle CHECKER"));
    let mut failures = 0;
    for (index, case) in CASES.iter().enumerate() {
        let allocator = Allocator::default();
        let parsed = Parser::new(&allocator, case.source, SourceType::ts()).parse();
        if !parsed.errors.is_empty() {
            eprintln!("OXC_REJECT {}: {:?}", case.name, parsed.errors);
            failures += 1;
            continue;
        }
        let mut expected = Shape::new();
        expected.visit_program(&parsed.program);

        let path = env::temp_dir().join(format!("react-hir-type-oracle-{}-{index}.ts", std::process::id()));
        fs::write(&path, case.source).expect("write oracle specimen");
        let result = Command::new(&checker).arg(&path).arg("--dump-ir").output()
            .expect("run Coil checker");
        let _ = fs::remove_file(&path);
        if !result.status.success() {
            eprintln!("COIL_REJECT {}: {}", case.name, String::from_utf8_lossy(&result.stdout));
            failures += 1;
            continue;
        }
        let dump = String::from_utf8(result.stdout).expect("Coil dump is UTF-8");
        let actual = coil_shape(&dump);
        if actual != expected.nodes {
            eprintln!("SHAPE_MISMATCH {}\n  oxc:  {:?}\n  coil: {:?}", case.name, expected.nodes, actual);
            failures += 1;
        } else {
            println!("ok {} nodes={}", case.name, actual.len());
        }
        let actual_spans = coil_spans(&dump);
        if actual_spans.len() != expected.spans.len() {
            eprintln!("SPAN_COUNT_MISMATCH {} expected={} actual={}",
                case.name, expected.spans.len(), actual_spans.len());
            failures += 1;
        } else {
            for (node_index, (expected_span, actual_span)) in
                expected.spans.iter().zip(&actual_spans).enumerate()
            {
                if expected_span.is_some_and(|span| span != *actual_span) {
                    eprintln!("SPAN_MISMATCH {} node={} kind={} expected={:?} actual={:?}",
                        case.name, node_index, expected.nodes[node_index], expected_span,
                        actual_span);
                    failures += 1;
                }
            }
        }
        for check in field_checks(case.name) {
            let actual = coil_metadata(&dump, check.opcode);
            let expected: Vec<_> = check.expected.iter().map(|&(operands, immediate)|
                Meta { operands, immediate }).collect();
            if actual != expected {
                eprintln!("FIELD_MISMATCH {} opcode={}\n  expected: {:?}\n  actual:   {:?}",
                    case.name, check.opcode, expected, actual);
                failures += 1;
            }
        }
    }
    assert_eq!(failures, 0, "{failures} TypeScript structural oracle failures");
    println!("typescript type oracle: {} cases passed", CASES.len());
}
