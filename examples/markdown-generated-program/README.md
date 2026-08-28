# Markdown-generated training planner

Every production module in this example begins as a Markdown specification:

- `arithmetic.md` describes reusable integer helpers.
- `training.md` describes the domain calculation and its dependency.
- `main.md` describes the executable and exact visible output.

Run `generate.sh` to materialize the three sibling `.coil` files in dependency
order with no contracts, build the final program, and execute it. The optional
`contracts/` directory demonstrates additional checks but is not needed to
generate or build the application.
