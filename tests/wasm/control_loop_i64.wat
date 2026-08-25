(module
  (func (export "before-loop") (param i64) (result i64)
    (local i64)
    i64.const 1
    local.set 1
    block
      loop
        local.get 0
        i64.eqz
        br_if 1
        local.get 0
        local.get 1
        i64.mul
        local.set 1
        local.get 0
        i64.const 1
        i64.sub
        local.set 0
        br 0
      end
    end
    local.get 1))
