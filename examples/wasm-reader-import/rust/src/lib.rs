#![no_std]

use core::panic::PanicInfo;

#[panic_handler]
fn panic(_info: &PanicInfo<'_>) -> ! {
    loop {}
}

/// Inspect four packed ASCII bytes and return three counters:
///
///     bits 16..23: uppercase letters
///     bits  8..15: vowels
///     bits  0..7:  decimal digits
#[unsafe(no_mangle)]
pub extern "C" fn analyze_ascii(mut packed: u32) -> u32 {
    let mut uppercase = 0u32;
    let mut vowels = 0u32;
    let mut digits = 0u32;
    let mut remaining = 4u32;

    while remaining != 0 {
        let byte = packed & 0xff;
        if byte >= b'A' as u32 && byte <= b'Z' as u32 {
            uppercase += 1;
        }
        if byte == b'A' as u32
            || byte == b'E' as u32
            || byte == b'I' as u32
            || byte == b'O' as u32
            || byte == b'U' as u32
        {
            vowels += 1;
        }
        if byte >= b'0' as u32 && byte <= b'9' as u32 {
            digits += 1;
        }

        packed >>= 8;
        remaining -= 1;
    }

    (uppercase << 16) | (vowels << 8) | digits
}
