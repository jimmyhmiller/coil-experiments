(module
  (type $binary (func (param i32 i32) (result i32)))
  (table 3 funcref)
  (func $add (type $binary) (param i32 i32) (result i32)
    local.get 0
    local.get 1
    i32.add)
  (func $sub (type $binary) (param i32 i32) (result i32)
    local.get 0
    local.get 1
    i32.sub)
  (elem (i32.const 1) $add $sub)
  (func (export "dispatch") (param i32 i32 i32) (result i32)
    local.get 1
    local.get 2
    local.get 0
    call_indirect (type $binary)))
