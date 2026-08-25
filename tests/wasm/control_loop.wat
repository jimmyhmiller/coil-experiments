(module
  (func (export "count") (param i32) (result i32)
    (local i32)
    loop (result i32)
      local.get 1
      local.get 0
      i32.eqz
      br_if 1
      local.get 1
      i32.const 1
      i32.add
      local.set 1
      local.get 0
      i32.const 1
      i32.sub
      local.set 0
      br 0
    end))
