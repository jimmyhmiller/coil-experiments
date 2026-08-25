(module
  (func (export "choose") (param i32) (result i32)
    block (result i32)
      i32.const 9
      local.get 0
      br_if 0
      i32.const 4
      i32.add
    end)
  (func (export "outer-choose") (param i32) (result i32)
    block (result i32)
      block (result i32)
        i32.const 44
        local.get 0
        br_if 1
        i32.const 1
        i32.add
      end
    end))
