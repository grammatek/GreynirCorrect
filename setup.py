#!/usr/bin/env python
# -*- encoding: utf-8 -*-
"""
    Greynir: Natural language processing for Icelandic

    Setup.py

    Copyright (C) 2020 Miðeind ehf.

        This program is free software: you can redistribute it and/or modify
        it under the terms of the GNU General Public License as published by
        the Free Software Foundation, either version 3 of the License, or
        (at your option) any later version.
        This program is distributed in the hope that it will be useful,
        but WITHOUT ANY WARRANTY; without even the implied warranty of
        MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
        GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see http://www.gnu.org/licenses/.


    This module sets up the ReynirCorrect package.

    Note that installing under PyPy >= 3.5 is supported.

"""

from __future__ import print_function
from __future__ import unicode_literals

import io
import re
import sys

from glob import glob
from os.path import basename, dirname, join, splitext

from setuptools import find_packages
from setuptools import setup


if sys.version_info < (3, 5):
    print("ReynirCorrect requires Python >= 3.5")
    sys.exit(1)


def read(*names, **kwargs):
    try:
        return io.open(
            join(dirname(__file__), *names),
            encoding=kwargs.get("encoding", "utf8")
        ).read()
    except (IOError, OSError):
        return ""


setup(
    name="reynir-correct",
    # Remember to update version in src/reynir_correct/__init__.py as well
    version="0.8.0",
    license="GNU GPLv3",
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
    url="https://github.com/mideind/ReynirCorrect",
    packages=find_packages("src"),
    package_dir={"": "src"},
    py_modules=[splitext(basename(path))[0] for path in glob("src/*.py")],
    package_data={"reynir_correct": ["py.typed"]},
    include_package_data=True,
    zip_safe=True,
    classifiers=[
        # complete classifier list: http://pypi.python.org/pypi?%3Aaction=list_classifiers
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)",
        "Operating System :: Unix",
        "Operating System :: POSIX",
        "Operating System :: Microsoft :: Windows",
        "Operating System :: MacOS",
        "Natural Language :: Icelandic",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: Implementation :: CPython",
        "Programming Language :: Python :: Implementation :: PyPy",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Utilities",
        "Topic :: Text Processing :: Linguistic",
    ],
    keywords=["nlp", "parser", "icelandic"],
    setup_requires=[],
    install_requires=["reynir>=2.2.0", "icegrams>=0.6.0"],
    # Set up a 'correct' command ('correct.exe' on Windows),
    # which calls main() in src/reynir-correct/main.py
    entry_points={
        'console_scripts': [
            'correct=reynir_correct.main:main',
        ],
    },
)
