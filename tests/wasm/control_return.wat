(module
  (func (export "top") (result i32)
    i32.const 41
    return
    i32.const 99)
  (func (export "from-block") (result i64)
    block (result i64)
      i64.const 42
      return
      i64.const 99
    end)
  (func (export "from-loop") (result f32)
    loop (result f32)
      f32.const 43
      return
      f32.const 99
    end))
