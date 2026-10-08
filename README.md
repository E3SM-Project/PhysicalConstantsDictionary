# PhysicalConstantsDictionary
YAML dictionary of physical constants and tools to create consistent constant sets for Earth System Models

To learn mode about this project, please read the available [documentation](https://github.com/ESCOMP/PhysicalConstantsDictionary/wiki). 

## Derived constants

An entry in `pcd.yaml` must define exactly one of `value` or `formula`:

- `value`: a plain numerical value, for constants that are not derived from
  other constants in the dictionary.
- `formula`: an arithmetic expression (`+`, `-`, `*`, `/`, `**`, unary `+`/`-`,
  and parentheses) referencing the `name` of one or more other constants in
  the dictionary, for constants that are derived from them. For example:

  ```yaml
  - name: molar_gas_constant
    formula: avogadro_constant * boltzmann_constant
  ```

`generate_source.py` never evaluates a `formula` itself: it validates that the
expression only uses arithmetic operators and known constant names, translates
it into the equivalent C++/Fortran expression, and lets the compiler compute
the actual value as a `constexpr`/`parameter`. This keeps derived constants
numerically consistent (to full double precision) with the constants they are
derived from, rather than relying on a separately hand-copied numerical value
that can drift out of sync.

Generated C++ headers require C++20.

The generator automatically orders every constant so that a derived
constant's `formula` only ever references constants declared earlier in the
generated file, regardless of the order groups/entries happen to appear in
`pcd.yaml`; a circular dependency between formulas is reported as an error.

`tools/validate_generated_sources.py` generates the C++ header and Fortran
module and attempts to compile a small driver program that references every
constant, as an extra safety net that generated formulas are valid, correctly
ordered code in both languages (it skips a language's check if that
language's compiler isn't available).

## Automated E3SM Updates

This repository includes a GitHub Actions workflow that automatically updates the E3SM repository when `pcd.yaml` is modified. 

When changes are pushed to `pcd.yaml` on the `main` branch, the workflow:
1. Generates updated source files (`pcd_const.f90` and `pcd_const.h`)
2. Creates a pull request in the [e3sm-project/e3sm](https://github.com/e3sm-project/e3sm) repository with:
   - Updated `share/util/pcd_const.f90` (Fortran module)
   - Updated `share/util_cxx/pcd_const.h` (C++ header)
   - Updated `share/pcd.yaml` (source YAML file)

**Note**: The workflow requires a GitHub personal access token (PAT) stored as a secret named `E3SM_PAT` with permissions to create pull requests in the e3sm-project/e3sm repository.
