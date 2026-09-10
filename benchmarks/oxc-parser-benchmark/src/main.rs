use std::{hint::black_box, time::Instant};

use oxc_allocator::Allocator;
use oxc_parser::Parser;
use oxc_span::SourceType;

const PATTERN: &str = "function compute(input) { let x = input + 10; while (x > 0) { x = x - 1; } if (x === 0) { return foo.state({value: [x, input]}); } else { return bar(input); } }\n";

fn report(name: &str, bytes: usize, rounds: usize, elapsed: std::time::Duration) {
    let gbps = bytes as f64 * rounds as f64 / elapsed.as_nanos() as f64;
    println!(
        "{name:20} {gbps:8.3} GB/s  size={bytes} rounds={rounds} ns={}",
        elapsed.as_nanos()
    );
}

fn main() {
    let repetitions = 1_000;
    let rounds = 100;
    let source = PATTERN.repeat(repetitions);
    let source_type = SourceType::mjs();

    let mut allocator = Allocator::default();
    let start = Instant::now();
    for _ in 0..rounds {
        allocator.reset();
        let parsed = Parser::new(&allocator, &source, source_type).parse();
        assert!(parsed.errors.is_empty());
        black_box(parsed.program.body.len());
    }
    report("oxc reset+parse", source.len(), rounds, start.elapsed());

    let start = Instant::now();
    for _ in 0..rounds {
        let allocator = Allocator::default();
        let parsed = Parser::new(&allocator, &source, source_type).parse();
        assert!(parsed.errors.is_empty());
        black_box(parsed.program.body.len());
    }
    report("oxc cold parse", source.len(), rounds, start.elapsed());
}
