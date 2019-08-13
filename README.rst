====
dtrx
====

----------------------------------
cleanly extract many archive types
----------------------------------

SYNOPSIS
========

.. code-block:: text

    dtrx [OPTIONS] ARCHIVE [ARCHIVE ...]

DESCRIPTION
===========

dtrx extracts archives in a number of different formats; it currently
supports tar, zip (including self-extracting .exe files), cpio, rpm, deb,
gem, 7z, cab, rar, lzh, arj, and InstallShield files.  It can also decompress
files compressed with gzip, bzip2, lzma, xz, lrzip, lzip, or compress.

In addition to providing one command to handle many different archive
types, dtrx also aids the user by extracting contents consistently.  By
default, everything will be written to a dedicated directory that's named
after the archive.  dtrx will also change the permissions to ensure that the
owner can read and write all those files.

To run dtrx, simply call it with the archive(s) you wish to extract as
arguments.  For example

.. code-block:: text

    $ dtrx coreutils-5.*.tar.gz

You may specify URLs as arguments as well.  If you do, dtrx will use ``wget
-c`` to download the URL to the current directory and then extract what it
downloads.  This may fail if you already have a file in the current
directory with the same name as the file you're trying to download.

OPTIONS
=======

dtrx supports a number of options to mandate specific behavior

.. code-block:: text

    -r, --recursive
        With this option, dtrx will search inside the archives you specify to see
        if any of the contents are themselves archives, and extract those as
        well.

    --one, --one-entry
        Normally, if an archive only contains one file or directory with a name
        that doesn't match the archive's, dtrx will ask you how to handle it.
        With this option, you can specify ahead of time what should happen.
        Possible values are:

        inside
            Extract the file/directory inside another directory named after the
            archive.  This is the default.

        rename
            Extract the file/directory in the current directory, and then rename
            it to match the name of the archive.

        here
            Extract the file/directory in the current directory.

    -o, --overwrite
        Normally, dtrx will avoid extracting into a directory that already exists,
        and instead try to find an alternative name to use.  If this option is
        listed, dtrx will use the default directory name no matter what.

    -f, --flat
        Extract all archive contents into the current directory, instead of
        their own dedicated directory.  This is handy if you have multiple
        archive files which all need to be extracted into the same directory
        structure.  Note that existing files may be overwritten with this
        option.

    -n, --noninteractive
        dtrx will normally ask the user how to handle certain corner cases, such
        as how to handle an archive that only contains one file.  This option
        suppresses those questions; dtrx will instead use sane, conservative
        defaults.

    -l, -t, --list, --table
        Don't extract the archives; just list their contents on standard output.

    -m, --metadata
        Extract the metadata from .deb and .gem archives, instead of their normal
        contents.

    -q, --quiet
        Suppress warning messages.  List this option twice to make dtrx silent.

    -v, --verbose
        Show the files that are being extracted.  List this option twice to
        print debugging information.

    --help
        Display basic help.

    --version
        Display dtrx's version, copyright, and license information.
