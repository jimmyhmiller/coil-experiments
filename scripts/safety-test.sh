#!/bin/sh
set -eu

safety_root=src/experiments/safety

coil test "$safety_root/arithmetic_test.coil" --meta-opt=0
coil test "$safety_root/dialect_test.coil" --meta-opt=0
coil test "$safety_root/sums_test.coil" --meta-opt=0
coil test "$safety_root/ffi_test.coil" --meta-opt=0
coil test "$safety_root/unsafe_test.coil" --meta-opt=0
coil run "$safety_root/demo.coil" --meta-opt=0
coil run "$safety_root/tests/unsafe_escape.coil" --meta-opt=0
coil run "$safety_root/tests/dynamic_dispatch_profile.coil" --meta-opt=0

run_trap() {
  safety_name=$1
  safety_want=$2
  safety_output=$(mktemp)

  if coil run "$safety_root/tests/$safety_name.coil" --meta-opt=0 >"$safety_output" 2>&1; then
    echo "expected $safety_name to trap" >&2
    rm -f "$safety_output"
    exit 1
  fi

  if ! grep -F "$safety_want" "$safety_output" >/dev/null; then
    echo "$safety_name trapped without expected diagnostic: $safety_want" >&2
    sed -n '1,20p' "$safety_output" >&2
    rm -f "$safety_output"
    exit 1
  fi

  rm -f "$safety_output"
  echo "trap ok: $safety_name"
}

run_trap bounds_trap "outside array"
run_trap debug_slice_bounds_trap "outside array"
run_trap debug_subslice_trap "invalid range"
run_trap arraylist_bounds_trap "outside array"
run_trap null_trap "invalid null pointer cast"
run_trap alignment_trap "is not aligned"
run_trap indirect_target_trap "not in a loaded image"
run_trap dynamic_dispatch_trap "null pointer dereference"
run_trap signed_cast_trap "outside cast range"
run_trap unsigned_cast_trap "outside cast range"
run_trap negative_unsigned_cast_trap "outside cast range"
run_trap float_cast_trap "outside integer cast range"
run_trap f32_cast_trap "outside integer cast range"
run_trap nan_cast_trap "outside integer cast range"
run_trap arithmetic_trap "addition overflow"
run_trap ubsan_add_trap "addition overflow"
run_trap operator_sub_trap "subtraction overflow"
run_trap operator_mul_trap "multiplication overflow"
run_trap operator_unsigned_add_trap "addition overflow"
run_trap operator_unsigned_sub_trap "subtraction overflow"
run_trap operator_unsigned_mul_trap "multiplication overflow"
run_trap operator_negation_trap "negation overflow"
run_trap primitive_iadd_trap "addition overflow"
run_trap primitive_isub_trap "subtraction overflow"
run_trap primitive_imul_trap "multiplication overflow"
run_trap primitive_idiv_trap "division by zero"
run_trap primitive_irem_trap "remainder by zero"
run_trap primitive_udiv_trap "division by zero"
run_trap primitive_urem_trap "remainder by zero"
run_trap primitive_ishl_trap "invalid shift amount"
run_trap primitive_ishr_trap "invalid shift amount"
run_trap volatile_alignment_trap "is not aligned"
run_trap volatile_store_alignment_trap "is not aligned"
run_trap bit_alignment_trap "is not aligned"
run_trap bit_set_alignment_trap "is not aligned"
run_trap ubsan_div_zero_trap "division by zero"
run_trap ubsan_rem_zero_trap "remainder by zero"
run_trap ubsan_div_overflow_trap "division overflow"
run_trap ubsan_shift_trap "invalid shift amount"
run_trap exact_div_trap "exact division has a remainder"
run_trap exact_shift_trap "exact right shift discards nonzero bits"
run_trap negation_trap "negation overflow"
run_trap small_exact_div_overflow_trap "conversion overflow"
run_trap small_shift_overflow_trap "left shift overflow"
run_trap unsigned_shift_overflow_trap "left shift overflow"
run_trap unreachable_trap "reached unreachable code"
run_trap option_unwrap_trap "attempted to unwrap None"
run_trap result_unwrap_trap "attempted to unwrap Err as Ok"
run_trap ffi_null_buffer_trap "nonempty buffer had null data"
run_trap ffi_unterminated_trap "no terminator"
run_trap ffi_overlap_trap "buffers overlap"

compile_fail() {
  safety_name=$1
  safety_want=$2
  safety_output=$(mktemp)

  if coil check "$safety_root/compile-fail/$safety_name.coil" >"$safety_output" 2>&1; then
    echo "expected $safety_name to fail compilation" >&2
    rm -f "$safety_output"
    exit 1
  fi

  if ! grep -F "$safety_want" "$safety_output" >/dev/null; then
    echo "$safety_name failed without expected diagnostic: $safety_want" >&2
    sed -n '1,20p' "$safety_output" >&2
    rm -f "$safety_output"
    exit 1
  fi

  rm -f "$safety_output"
  echo "compile failure ok: $safety_name"
}

compile_fail non_exhaustive_match "non-exhaustive match"
compile_fail missing_return "body has type void"
compile_fail constant_bounds "statically known array index is out of bounds"
compile_fail constant_null "statically known null pointer cast"
compile_fail constant_null_indirect "statically known null indirect call target"
compile_fail stack_local_return "pointer derived from stack storage"
compile_fail stack_local_alias_return "pointer derived from stack storage"
compile_fail generic_stack_return "pointer derived from stack storage"
compile_fail raw_pointer_index "indexing a pointer without a statically known length requires unsafe"
compile_fail alias_load "unverifiable primitive requires an explicit unsafe wrapper"
compile_fail alias_store "unverifiable primitive requires an explicit unsafe wrapper"
compile_fail llvm_ir "unverifiable primitive requires an explicit unsafe wrapper"
compile_fail raw_free "unverifiable primitive requires an explicit unsafe wrapper"
compile_fail nonstandard_integer_cast "conversion involving a nonstandard integer width requires unsafe"
compile_fail nonstandard_integer_arithmetic "arithmetic on a nonstandard integer width requires unsafe"
compile_fail zeroed_value "unverifiable primitive requires an explicit unsafe wrapper"

echo "all safety dialect tests passed"
