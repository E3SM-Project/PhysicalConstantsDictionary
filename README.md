# PhysicalConstantsDictionary
YAML dictionary of physical constants and tools to create consistent constant sets for Earth System Models

To learn mode about this project, please read the available [documentation](https://github.com/ESCOMP/PhysicalConstantsDictionary/wiki). 

## Automated E3SM Updates

This repository includes a GitHub Actions workflow that automatically updates the E3SM repository when `pcd.yaml` is modified. 

When changes are pushed to `pcd.yaml` on the `main` branch, the workflow:
1. Generates updated source files (`pcd_const.f90` and `pcd_const.h`)
2. Creates a pull request in the [e3sm-project/e3sm](https://github.com/e3sm-project/e3sm) repository with:
   - Updated `share/util/pcd_const.f90` (Fortran module)
   - Updated `share/util_cxx/pcd_const.h` (C++ header)
   - Updated `share/pcd.yaml` (source YAML file)

**Note**: The workflow requires a GitHub personal access token (PAT) stored as a secret named `E3SM_PAT` with permissions to create pull requests in the e3sm-project/e3sm repository.
