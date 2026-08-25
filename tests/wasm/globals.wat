(module
  (global $constant i64 (i64.const -5))
  (global $counter (mut i32) (i32.const -12))
  (export "constant-global" (global $constant))
  (export "counter-global" (global $counter))
  (func (export "constant") (result i64)
    global.get $constant)
  (func (export "get") (result i32)
    global.get $counter)
  (func (export "set") (param i32) (result i32)
    local.get 0
    global.set $counter
    global.get $counter)
  (func (export "add") (param i32) (result i32)
    global.get $counter
    local.get 0
    i32.add))
