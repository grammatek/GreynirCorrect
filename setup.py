#!/usr/bin/env python
# -*- encoding: utf-8 -*-
"""
    Greynir: Natural language processing for Icelandic

    Setup.py

    Copyright (C) 2022 Miðeind ehf.
    Original author: Vilhjálmur Þorsteinsson

    This software is licensed under the MIT License:

        Permission is hereby granted, free of charge, to any person
        obtaining a copy of this software and associated documentation
        files (the "Software"), to deal in the Software without restriction,
        including without limitation the rights to use, copy, modify, merge,
        publish, distribute, sublicense, and/or sell copies of the Software,
        and to permit persons to whom the Software is furnished to do so,
        subject to the following conditions:

        The above copyright notice and this permission notice shall be
        included in all copies or substantial portions of the Software.

        THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
        EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
        MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
        IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
        CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
        TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
        SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.


    This module sets up the GreynirCorrect package and installs the
    'correct' command-line utility.

    This package requires Python >= 3.7, and supports PyPy >= 3.7.

"""

from __future__ import print_function
from __future__ import unicode_literals

import io
import re
import sys

from glob import glob
from os.path import basename, dirname, join, splitext

from setuptools import find_packages  # type: ignore
from setuptools import setup  # type: ignore


if sys.version_info < (3, 7):
    print("GreynirCorrect requires Python >= 3.7")
    sys.exit(1)


def read(*names: str, **kwargs: str):
    try:
        return io.open(
            join(dirname(__file__), *names),
            encoding=kwargs.get("encoding", "utf8")
        ).read()
    except (IOError, OSError):
        return ""

# Load version string from file
__version__ = "[missing]"
exec(open(join("src", "reynir_correct", "version.py")).read())

setup(
    name="reynir-correct",
    version=__version__,
    license="MIT",
    description="A spelling and grammar corrector for Icelandic",
    long_description="{0}\n{1}".format(
        re
            .compile("^.. start-badges.*^.. end-badges", re.M | re.S)
            .sub("", read("README.rst")),
        re
            .sub(":[a-z]+:`~?(.*?)`", r"``\1``", read("CHANGELOG.rst")),
    ),
    author="Miðeind ehf",
    author_email="mideind@mideind.is",
    url="https://github.com/mideind/GreynirCorrect",
    packages=find_packages("src"),
    package_dir={"": "src"},
    py_modules=[splitext(basename(path))[0] for path in glob("src/*.py")],
    package_data={"reynir_correct": ["py.typed"]},
    include_package_data=True,
    zip_safe=True,
    classifiers=[
        # complete classifier list: http://pypi.python.org/pypi?%3Aaction=list_classifiers
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: MIT License",
        "Operating System :: Unix",
        "Operating System :: POSIX",
        "Operating System :: Microsoft :: Windows",
        "Operating System :: MacOS",
        "Natural Language :: Icelandic",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: Implementation :: CPython",
        "Programming Language :: Python :: Implementation :: PyPy",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Utilities",
        "Topic :: Text Processing :: Linguistic",
    ],
    keywords=["nlp", "parser", "icelandic"],
    setup_requires=[],
    install_requires=["reynir>=3.4.0", "icegrams>=1.1.0", "typing_extensions"],
    # Set up a 'correct' command ('correct.exe' on Windows),
    # which calls main() in src/reynir-correct/main.py
    entry_points={
        'console_scripts': [
            'correct=reynir_correct.main:main',
        ],
    },
)
