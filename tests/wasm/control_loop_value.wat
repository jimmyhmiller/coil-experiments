(module
  (func (export "unary") (result i32)
    loop (result i32)
      i32.const 12
    end
    i32.ctz)
  (func (export "binary") (result i32)
    loop (result i32)
      i32.const 6
    end
    loop (result i32)
      i32.const 7
    end
    i32.mul))
