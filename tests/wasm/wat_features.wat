(module
  (func (export "named-add") (param $left i32) (param $right i32) (result i32)
    local.get $left
    local.get $right
    i32.add)
  (func (export "i32-constant") (result i32)
    i32.const -1)
  (func (export "i64-constant") (result i64)
    i64.const 9223372036854775807)
  (func (export "f32-constant") (result f32)
    f32.const 1.5)
  (func (export "f64-constant") (result f64)
    f64.const 1.5))
