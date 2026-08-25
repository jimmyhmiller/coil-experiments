(module
  (func (export "branch-table") (param i32) (result i32)
    block (result i32)
      i32.const 42
      local.get 0
      br_table 0 0
      i32.const 99
    end))
