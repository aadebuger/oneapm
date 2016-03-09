from __future__ import print_function

import sys
import os

python_version = sys.version_info[:2]

assert python_version in ((2, 6), (2, 7)) or python_version >= (3, 3), \
        'The Blueware Python agent only supports Python 2.6, 2.7 and 3.3+.'

with_setuptools = False

try:
    from setuptools import setup
    with_setuptools = True
except ImportError:
    from distutils.core import setup

from distutils.core import Extension
from distutils.command.build_ext import build_ext
from distutils.errors import (CCompilerError, DistutilsExecError,
        DistutilsPlatformError)

copyright = '(C) Copyright 2013-2015 Blueware Inc. All rights reserved.'

package_version = '1.0.10'

if sys.platform == 'win32' and python_version > (2, 6):
    build_ext_errors = (CCompilerError, DistutilsExecError,
            DistutilsPlatformError, IOError)
else:
    build_ext_errors = (CCompilerError, DistutilsExecError,
            DistutilsPlatformError)

class BuildExtFailed(Exception):
    pass

class optional_build_ext(build_ext):
    def run(self):
        try:
            build_ext.run(self)
        except DistutilsPlatformError:
            raise BuildExtFailed()

    def build_extension(self, ext):
        try:
            build_ext.build_extension(self, ext)
        except build_ext_errors:
            raise BuildExtFailed()

packages = [
  "blueware",
  "blueware.admin",
  "blueware.api",
  "blueware.bootstrap",
  "blueware.common",
  "blueware.core",
  "blueware.extras",
  "blueware.extras.framework_django",
  "blueware.extras.framework_django.templatetags",
  "blueware.hooks",
  "blueware.hooks.framework_tornado",
  "blueware.hooks.framework_django",
  "blueware.hooks.framework_django.contrib",
  "blueware.hooks.framework_django.contrib.staticfiles",
  "blueware.hooks.framework_django.core",
  "blueware.hooks.framework_django.core.handlers",
  "blueware.hooks.framework_django.core.mail",
  "blueware.hooks.framework_django.core.management",
  "blueware.hooks.framework_django.core.servers",
  "blueware.hooks.framework_django.http",
  "blueware.hooks.framework_django.template",
  "blueware.hooks.framework_django.views",
  "blueware.hooks.framework_django.views.generic",
  "blueware.hooks/framework_twisted",
  "blueware.hooks/framework_twisted.web",
  "blueware.hooks/framework_twisted.internet",
  "blueware.hooks.framework_cyclone",
  "blueware.network",
  "blueware/packages",
  "blueware/packages/requests",
  "blueware/packages/requests/packages",
  "blueware/packages/requests/packages/chardet",
  "blueware/packages/requests/packages/urllib3",
  "blueware/packages/requests/packages/urllib3/packages",
  "blueware/packages/requests/packages/urllib3/packages/ssl_match_hostname",
  "blueware/packages/requests/packages/urllib3/util",
  "blueware/packages/wrapt",
  "blueware.samplers",
]

kwargs = dict(
  name="blueware",
  version=package_version,
  description="Python agent for OneAPM",
  author="OneAPM",
  author_email="support@oneapm.com",
  license=copyright,
  url="http://www.oneapm.com",
  packages=packages,
  package_data={'blueware': ['blueware.ini', 'LICENSE',
          'packages/requests/LICENSE', 'packages/requests/NOTICE',
          'packages/requests/cacert.pem']},
  extra_path=("blueware", "blueware-%s" % package_version),
  scripts=['scripts/blueware-admin'],
)

if with_setuptools:
    kwargs['entry_points'] = {
            'console_scripts': ['blueware-admin = blueware.admin:main'],
            }

def with_librt():
    try:
        if sys.platform.startswith('linux'):
            import ctypes.util
            return ctypes.util.find_library('rt')
    except Exception:
        pass

def run_setup(with_extensions):
    def _run_setup():
        kwargs_tmp = dict(kwargs)

        if with_extensions:
            monotonic_libraries = []
            if with_librt():
                monotonic_libraries = ['rt']

            kwargs_tmp['ext_modules'] = [
                    Extension("blueware.packages.wrapt._wrappers",
                        ["blueware/packages/wrapt/_wrappers.c"]),
                    Extension("blueware.common._monotonic",
                        ["blueware/common/_monotonic.c"],
                        libraries=monotonic_libraries),
                    Extension("blueware.core._thread_utilization",
                        ["blueware/core/_thread_utilization.c"]),
                    ]
            kwargs_tmp['cmdclass'] = dict(build_ext=optional_build_ext)

        setup(**kwargs_tmp)

    if os.environ.get('TDDIUM') is not None:
        try:
            print('INFO: Running under tddium. Use lock.')
            from lock_file import LockFile
        except ImportError:
            print('ERROR: Cannot import locking mechanism.')
            _run_setup()
        else:
            print('INFO: Attempting to create lock file.')
            with LockFile('setup.lock', wait=True):
                _run_setup()
    else:
        _run_setup()

WARNING = """
WARNING: The optional C extension components of the Python agent could
not be compiled. This can occur where a compiler is not present on the
target system or the Python installation does not have the corresponding
developer package installed. The Python agent will instead be installed
without the extensions. The consequence of this is that although the
Python agent will still run, some non core features of the Python agent,
such as capacity analysis instance busy metrics, will not be available.
Pure Python versions of code supporting some features, rather than the
optimised C versions, will also be used resulting in additional overheads.
"""

with_extensions = os.environ.get('BLUEWARE_EXTENSIONS', None)
if with_extensions:
    if with_extensions.lower() == 'true':
        with_extensions = True
    elif with_extensions.lower() == 'false':
        with_extensions = False
    else:
        with_extensions = None

if hasattr(sys, 'pypy_version_info'):
    with_extensions = False

if with_extensions is not None:
    run_setup(with_extensions=with_extensions)

else:
    try:
        run_setup(with_extensions=True)

    except BuildExtFailed:

        print(75 * '*')

        print(WARNING)
        print("INFO: Trying to build without extensions.")

        print()
        print(75 * '*')

        run_setup(with_extensions=False)

        print(75 * '*')

        print(WARNING)
        print("INFO: Only pure Python agent was installed.")

        print()
        print(75 * '*')
