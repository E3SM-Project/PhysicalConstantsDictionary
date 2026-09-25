#!/usr/bin/env python3

"""
Sanity-check the source files generated from pcd.yaml.

This script:
  1. Runs generate_source.py to produce a C++ header and a Fortran module
     from the current pcd.yaml.
  2. Writes a tiny driver program in each language that references every
     single generated constant, so that a bad 'formula' (e.g. one that
     compiles as Python but not as C++/Fortran, or a dependency-ordering
     bug that slipped through) is caught by an actual compiler rather than
     only by generate_source.py's own (best-effort) validation.
  3. Compiles each driver with a C++ and a Fortran compiler, if one is
     available on the PATH. If a compiler isn't found, the corresponding
     check is skipped with a warning (rather than failing), so this script
     can still be run in environments that only have one of the two
     toolchains installed.

Exits with a non-zero status if any available compiler fails to build its
driver program.
"""

import argparse
import pathlib
import shutil
import subprocess
import sys
import tempfile

this_script_dir = pathlib.Path(__file__).parent
sys.path.insert(0, str(this_script_dir))

import generate_source  # noqa: E402


###############################################################################
def write_cxx_driver(path, header_name, names):
###############################################################################
    with open(path, 'w', encoding='utf-8') as f:
        f.write(f'#include "{header_name}"\n\n')
        f.write('int main() {\n')
        f.write('    double sum = 0.0;\n')
        for n in names:
            f.write(f'    sum += pcd::{n};\n')
        f.write('    return sum == sum ? 0 : 1;\n')
        f.write('}\n')


###############################################################################
def write_f90_driver(path, module_name, names):
###############################################################################
    with open(path, 'w', encoding='utf-8') as f:
        f.write(f'program pcd_validate\n')
        f.write(f'    use {module_name}\n')
        f.write('    implicit none\n')
        f.write('    real(dp) :: total\n\n')
        f.write('    total = 0.0_dp\n')
        for n in names:
            f.write(f'    total = total + {n}\n')
        f.write('    if (total /= total) stop 1\n')
        f.write('end program pcd_validate\n')


###############################################################################
def validate_cxx(workdir, names):
###############################################################################
    compiler = shutil.which('g++') or shutil.which('c++') or shutil.which('clang++')
    if compiler is None:
        print('SKIP: no C++ compiler found on PATH; skipping C++ validation.')
        return True

    header = workdir / 'pcd_const.h'
    generate_source.generate_file('cxx', None, str(header))

    driver = workdir / 'pcd_validate.cc'
    write_cxx_driver(driver, header.name, names)

    exe = workdir / 'pcd_validate_cxx'
    result = subprocess.run(
        [compiler, '-std=c++14', '-Wall', '-Wextra', '-Werror', '-I', str(workdir),
         str(driver), '-o', str(exe)],
        cwd=workdir, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        print('FAIL: generated C++ header failed to compile:')
        print(result.stdout)
        print(result.stderr)
        return False

    print(f'OK: generated C++ header compiles cleanly with {compiler}.')
    return True


###############################################################################
def validate_f90(workdir, names):
###############################################################################
    compiler = shutil.which('gfortran') or shutil.which('f90')
    if compiler is None:
        print('SKIP: no Fortran compiler found on PATH; skipping Fortran validation.')
        return True

    module = workdir / 'pcd_const.F90'
    generate_source.generate_file('f90', None, str(module))

    driver = workdir / 'pcd_validate.F90'
    write_f90_driver(driver, 'pcd', names)

    exe = workdir / 'pcd_validate_f90'
    result = subprocess.run(
        [compiler, '-Wall', '-Werror', '-J', str(workdir), '-I', str(workdir),
         str(module), str(driver), '-o', str(exe)],
        cwd=workdir, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        print('FAIL: generated Fortran module failed to compile:')
        print(result.stdout)
        print(result.stderr)
        return False

    print(f'OK: generated Fortran module compiles cleanly with {compiler}.')
    return True


###############################################################################
def main():
###############################################################################
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()

    _, _, _, all_items, _ = generate_source.load_constants(None)
    names = [it['name'] for it in all_items]

    with tempfile.TemporaryDirectory(prefix='pcd_validate_') as tmp:
        workdir = pathlib.Path(tmp)
        ok_cxx = validate_cxx(workdir, names)
        ok_f90 = validate_f90(workdir, names)

    if not (ok_cxx and ok_f90):
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
