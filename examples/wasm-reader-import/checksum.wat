(module
  ;; A small rolling hash. This deliberately uses a mutable WASM local so the
  ;; reader has to compile stateful stack-machine code, not one arithmetic form.
  (func (export "checksum")
        (param $a i32) (param $b i32) (param $c i32) (param $d i32)
        (result i32)
    (local $hash i32)

    local.get $a
    local.set $hash

    local.get $hash
    i32.const 31
    i32.mul
    local.get $b
    i32.add
    local.set $hash

    local.get $hash
    i32.const 31
    i32.mul
    local.get $c
    i32.add
    local.set $hash

    local.get $hash
    i32.const 31
    i32.mul
    local.get $d
    i32.add
    local.set $hash

    local.get $hash))
