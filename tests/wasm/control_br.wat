(module
  (func (export "branch") (result i32)
    block (result i32)
      i32.const 42
      br 0
      i32.const 99
    end)
  (func (export "outer-branch") (result i32)
    block (result i32)
      block
        i32.const 43
        br 1
      end
      i32.const 99
    end))
