use std::{env, fs, path::PathBuf, process::Command};

use oxc_allocator::Allocator;
use oxc_ast::ast::{
    TSOptionalType, TSRestType, TSSignature, TSType,
};
use oxc_ast_visit::{walk, Visit};
use oxc_parser::Parser;
use oxc_span::SourceType;

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
];

struct Shape {
    nodes: Vec<&'static str>,
}

impl Shape {
    fn new() -> Self { Self { nodes: Vec::new() } }
}

impl<'a> Visit<'a> for Shape {
    fn visit_ts_type(&mut self, ty: &TSType<'a>) {
        // Oxc stores entity-name leaves as fields. Coil makes those leaves SSA
        // values when another operation (type arguments, a predicate, or an
        // import qualifier) must own them, so include that explicit lowering in
        // the normalized Oxc projection before visiting child types.
        match ty {
            TSType::TSTypeReference(node) if node.type_arguments.is_some() =>
                self.nodes.push("ts.type_reference"),
            TSType::TSTypeQuery(node) if node.type_arguments.is_some() =>
                self.nodes.push("ts.type_reference"),
            TSType::TSImportType(node) if node.qualifier.is_some() =>
                self.nodes.push("ts.type_reference"),
            TSType::TSTypePredicate(_) => self.nodes.push("ts.type_reference"),
            _ => {}
        }
        walk::walk_ts_type(self, ty);
        self.nodes.push(match ty {
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
        });
    }

    fn visit_ts_optional_type(&mut self, ty: &TSOptionalType<'a>) {
        walk::walk_ts_optional_type(self, ty);
        self.nodes.push("ts.optional_type");
    }

    fn visit_ts_rest_type(&mut self, ty: &TSRestType<'a>) {
        walk::walk_ts_rest_type(self, ty);
        self.nodes.push("ts.rest_type");
    }

    fn visit_ts_signature(&mut self, signature: &TSSignature<'a>) {
        walk::walk_ts_signature(self, signature);
        self.nodes.push(match signature {
            TSSignature::TSIndexSignature(_) => "ts.index_signature",
            TSSignature::TSPropertySignature(_) => "ts.property_signature",
            TSSignature::TSCallSignatureDeclaration(_) => "ts.call_signature",
            TSSignature::TSConstructSignatureDeclaration(_) => "ts.construct_signature",
            TSSignature::TSMethodSignature(_) => "ts.method_signature",
        });
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
    }
    assert_eq!(failures, 0, "{failures} TypeScript structural oracle failures");
    println!("typescript type oracle: {} cases passed", CASES.len());
}
