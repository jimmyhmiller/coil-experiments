(module
  (func (export "branch") (result i32)
    block (result i32)
      i32.const 42
      br 0
      i32.const 99
    end))
