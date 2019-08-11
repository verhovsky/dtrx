#!/usr/bin/env python

from distutils.core import setup

setup(
    name="dtrx",
    version="9.0",
    description="Script to intelligently extract multiple archive types",
    author="Brett Smith",
    author_email="brettcsmith@brettcsmith.org",
    url="https://github.com/verhovsky/dtrx",
    download_url="https://github.com/verhovsky/dtrx",
    scripts=["scripts/dtrx"],
    license="GNU General Public License, version 3 or later",
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Environment :: Console",
        "Intended Audience :: End Users/Desktop",
        "Intended Audience :: System Administrators",
        "License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)",
        "Natural Language :: English",
        "Operating System :: POSIX",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3 :: Only",
        "Topic :: Utilities",
    ],
    long_description="""dtrx extracts archives in a number of different
      formats; it currently supports tar, zip (including self-extracting
      .exe files), cpio, rpm, deb, gem, 7z, cab, rar, lzh, arj, and
      InstallShield files.  It can also decompress files compressed with gzip,
      bzip2, lzma, xz, lrzip, lzip, or compress.

      In addition to providing one command to handle many different archive
      types, dtrx also aids the user by extracting contents consistently.
      By default, everything will be written to a dedicated directory
      that's named after the archive.  dtrx will also change the
      permissions to ensure that the owner can read and write all those
      files.""",
)
