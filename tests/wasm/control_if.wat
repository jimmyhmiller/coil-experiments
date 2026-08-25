(module
  (func (export "choose") (param i32) (result i32)
    local.get 0
    if (result i32)
      i32.const 11
    else
      i32.const 22
    end))
