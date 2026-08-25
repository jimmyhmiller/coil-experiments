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
    end)
  (func (export "from-if-then") (param i32 i32) (result i32)
    local.get 0
    if (result i32)
      i32.const 3
      return
    else
      local.get 1
    end)
  (func (export "from-if-else") (param i32 i32) (result i32)
    local.get 0
    if (result i32)
      local.get 1
    else
      i32.const 4
      return
    end))
