(module
  (memory 1 2)
  (data (i32.const 8) "\01\02\03\04")
  (func (export "size") (result i32)
    memory.size)
  (func (export "grow") (param i32) (result i32)
    local.get 0
    memory.grow)
  (func (export "load") (param i32) (result i32)
    local.get 0
    i32.load)
  (func (export "data") (result i32)
    i32.const 8
    i32.load)
  (func (export "store-load") (param i32 i32) (result i32)
    local.get 0
    local.get 1
    i32.store
    local.get 0
    i32.load)
  (func (export "narrow") (param i32 i32) (result i32)
    local.get 0
    local.get 1
    i32.store16
    local.get 0
    i32.load16_u))
