use std::{
    env, fs,
    path::{Path, PathBuf},
    process::Command,
};

use oxc_allocator::Allocator;
use oxc_parser::Parser;
use oxc_span::SourceType;

fn collect(path: &Path, files: &mut Vec<PathBuf>) {
    if path.is_dir() {
        let mut entries: Vec<_> = fs::read_dir(path)
            .unwrap_or_else(|error| panic!("cannot read {}: {error}", path.display()))
            .map(|entry| entry.expect("invalid directory entry").path())
            .collect();
        entries.sort();
        for entry in entries {
            if entry.file_name().is_some_and(|name| {
                matches!(name.to_str(), Some("node_modules" | ".git" | ".next" | "dist" | "build"))
            }) {
                continue;
            }
            collect(&entry, files);
        }
    } else if matches!(path.extension().and_then(|value| value.to_str()), Some("ts" | "tsx")) {
        files.push(path.to_owned());
    }
}

fn main() {
    let mut args = env::args_os().skip(1);
    let checker = PathBuf::from(args.next().expect("usage: typescript-coverage CHECKER PATH..."));
    let roots: Vec<PathBuf> = args.map(PathBuf::from).collect();
    assert!(!roots.is_empty(), "usage: typescript-coverage CHECKER PATH...");

    let mut files = Vec::new();
    for root in &roots {
        collect(root, &mut files);
    }
    files.sort();
    files.dedup();

    let mut reference_files = 0usize;
    let mut reference_bytes = 0usize;
    let mut passed_files = 0usize;
    let mut passed_bytes = 0usize;
    let mut failures = Vec::new();

    for path in files {
        let source = fs::read_to_string(&path)
            .unwrap_or_else(|error| panic!("cannot read {}: {error}", path.display()));
        let source_type = SourceType::from_path(&path)
            .unwrap_or_else(|_| panic!("unsupported source type: {}", path.display()));
        let allocator = Allocator::default();
        let parsed = Parser::new(&allocator, &source, source_type).parse();
        if !parsed.errors.is_empty() {
            eprintln!("REFERENCE_REJECT {} errors={}", path.display(), parsed.errors.len());
            continue;
        }

        reference_files += 1;
        reference_bytes += source.len();
        let output = Command::new(&checker)
            .arg(&path)
            .output()
            .unwrap_or_else(|error| panic!("cannot run {}: {error}", checker.display()));
        if output.status.success() {
            passed_files += 1;
            passed_bytes += source.len();
        } else {
            let diagnostic = String::from_utf8_lossy(&output.stdout).trim().to_owned();
            failures.push((path, source.len(), diagnostic));
        }
    }

    let file_percent = if reference_files == 0 {
        0.0
    } else {
        passed_files as f64 * 100.0 / reference_files as f64
    };
    let byte_percent = if reference_bytes == 0 {
        0.0
    } else {
        passed_bytes as f64 * 100.0 / reference_bytes as f64
    };
    println!(
        "coverage files={passed_files}/{reference_files} ({file_percent:.2}%) bytes={passed_bytes}/{reference_bytes} ({byte_percent:.2}%)"
    );
    println!("failures={}", failures.len());
    for (path, bytes, diagnostic) in failures.iter().take(40) {
        println!("FAIL bytes={bytes} {} :: {diagnostic}", path.display());
    }
}
