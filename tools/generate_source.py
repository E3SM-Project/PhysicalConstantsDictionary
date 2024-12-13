#!/usr/bin/env python3

"""
Scripts to generate source-code files from the pcd.yaml file

The script is intended to be used by Earth System Model applications
to generate valid source code files to be used throughout the code.
The goal is to ensure that different parts of the project (and possibly
different projects) all agree on the numerical value of common
physical constants.

As of 12/2024, the script supports generting a C++ header or a F90 module.
"""

import sys
import pathlib
import argparse
import yaml

this_script_dir = pathlib.Path(__file__).parent

###############################################################################
def parse_command_line(args, description):
###############################################################################
    """
    Parse command line arguments
    """
    parser = argparse.ArgumentParser(
        usage=f"\n{pathlib.Path(args[0]).name} <ARGS> [--verbose]\n\n"
               "EXAMPLES\n\n"
               "   # Generate the Fortran90 module 'constants.F90' with all constants.\n"
               "   > {0} --lang f90 -o constants.F90\n"
               "   # Generate the C++ header 'constants.h' with only 'mathematics' constants\n"
               "   > {0} --lang cxx --groups mathematics -f constants.h\n",
        description=description)

    langs = ['cxx','f90']
    parser.add_argument('-l', '--lang',
                        help='Language for which to enerate.',
                        type=str, choices=langs, required=True)
    parser.add_argument('-g', '--groups',
                        help='Groups to include in the generated file (optional).'
                             'If not provided, include all groups', nargs='+')
    parser.add_argument('-f', '--filename',
                        help='Name of the generated output file',
                        type=str, required=True)

    return parser.parse_args(args[1:])

###############################################################################
def write_header(ofile,lang):
###############################################################################
    """
    Write file header
    """
    if lang=='cxx':
        ofile.write('#ifndef PHYSICAL_CONSTANTS_DICTIONARY_HPP\n')
        ofile.write('#define PHYSICAL_CONSTANTS_DICTIONARY_HPP\n\n')
        ofile.write('namespace pcd {\n')
    elif lang=='f90':
        ofile.write('module pcd\n')
        ofile.write('    implicit none\n\n')
        ofile.write('    !define double precision kind\n')
        ofile.write('    integer, parameter :: dp = selected_real_kind(12)\n')
    else:
        raise RuntimeError(f'Missing implementation for language {lang}')

###############################################################################
def write_footer(ofile,lang):
###############################################################################
    """
    Write file footer
    """
    if lang=='cxx':
        ofile.write('\n} // namespace pcd \n')
        ofile.write('#endif // PHYSICAL_CONSTANTS_DICTIONARY')
    elif lang=='f90':
        ofile.write('\nend module pcd')
    else:
        raise RuntimeError(f'Missing implementation for language {lang}')

###############################################################################
def write_group(ofile,lang,gname,group):
###############################################################################
    """
    Write constants from a single group
    """
    if lang=='cxx':
        ofile.write(f'\n// {gname} constants\n')
    elif lang=='f90':
        ofile.write(f'\n    !{gname} constants\n')
    else:
        raise RuntimeError(f'Missing implementation for language {lang}')

    for c in group['entries']:
        n = c['name']
        v = c['value']
        if lang=='cxx':
            ofile.write (f'constexpr double {n} = {v};\n')
        elif lang=='f90':
            ofile.write (f'    real(dp), parameter :: {n} = {v}_dp\n')
        else:
            raise RuntimeError(f'Missing implementation for language {lang}')

###############################################################################
def generate_file(lang,groups,filename):
###############################################################################
    """
    Parse the pcd.yaml file, and dump to file the content of the requested groups
    """

    with open(this_script_dir.parent / "pcd.yaml", 'r', encoding="utf-8") as fd:
        constants_dict = yaml.safe_load(fd)['physical_constants_dictionary']

    groups_in_file = {}
    for g in constants_dict['set']:
        if len(g.keys())>1:
            raise ValueError('Invalid formatting of pcd database.\n'
                             'Each entry of the "set" sequence should contain ONE dictionary')
        for k,v in g.items():
            groups_in_file[k] = v
    valid_groups = list(groups_in_file.keys())
    if groups is not None and any(item not in valid_groups for item in groups):
        raise ValueError(f"Invalid value for groups: {','.join(groups)}.\n"
                         f"Valid choices are {','.join(valid_groups)}")

    with open(filename,'w', encoding="utf-8") as ofile:
        # Header
        write_header(ofile,lang)

        # Content, by group
        for gname,group in groups_in_file.items():
            if groups is None or gname in groups:
                write_group(ofile,lang,gname,group)

        # Footer
        write_footer (ofile,lang)


###############################################################################
def _main_func(description):
###############################################################################
    generate_file(**vars(parse_command_line(sys.argv, description)))
    sys.exit(0)

###############################################################################

if __name__ == "__main__":
    _main_func(__doc__)
