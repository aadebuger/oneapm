from __future__ import print_function

from blueware.admin import command, usage

@command('license-info', '',
"""Prints out the LICENSE for the blueware Python Agent.""")
def license_info(args):
    import os
    import sys

    if len(args) != 0:
        usage('license-info')
        sys.exit(1)

    from blueware import __file__ as package_root
    package_root = os.path.dirname(package_root)

    license_file = os.path.join(package_root, 'LICENSE')

    license = open(license_file, 'r').read()

    print(license, end='')
