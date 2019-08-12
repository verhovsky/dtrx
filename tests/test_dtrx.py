#!/usr/bin/env python3
#
# compare.py -- High-level tests for dtrx.
# Copyright © 2006-2009 Brett Smith <brettcsmith@brettcsmith.org>.
#
# This program is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation; either version 3 of the License, or (at your
# option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, see <http://www.gnu.org/licenses/>.

# TODO: run each test from a nested directory as well

import os
import shutil
import re
import subprocess
import sys
import tempfile
import termios
from pathlib import Path
import pytest
from pprint import pprint

TEST_FILES_PATH = Path("tests").absolute()

if not TEST_FILES_PATH.is_dir():
    sys.exit(f"ERROR: missing test directory {str(TEST_FILES_PATH)}")

DTRX_SCRIPT = Path("scripts/dtrx").absolute()

# -s stdin
#       Read commands from standard input (set automatically if no file arguments are present)
# -e errexit
#       exit immediately if any untested command fails
SHELL_CMD = ["sh", "-se"]
ROOT_DIR = Path().absolute()


def run_command(command, input=None, prerun=None):
    if prerun is not None:
        prerun_result = subprocess.run(
            prerun, shell=True, capture_output=True, text=True
        )
        assert prerun_result.returncode == 0

    # pass `input` as stdin to an `sh` command
    # get subprocess.run to type it in, letter by letter
    return subprocess.run(command, input=input, capture_output=True, text=True)


def copyfile(src, dst):
    if not src.exists():
        print(f"file '{src}'' doesn't exist, skipping")
        return
    return shutil.copyfile(src, dst)


def list_all_files(directory):
    directory = directory.absolute()
    return {f.relative_to(directory) for f in directory.glob("**/*")}


def call_test(
    # path to the temporary directory where the compressed files are placed and
    # where dtrx is run from (with os.chrdir())
    tmp_path,
    # options passed to `dtrx`
    # -n is non-interactive mode, to enable interactive mode pass options=""
    # TODO: maybe automatically detect that there's `input` and remove "-n" flag?
    #     maybe?
    options="-n",
    # which compressed files (from the tests directory) are used in this test
    filenames="",
    # TODO: this was needed in the old tests because they would create a directory called either
    # "inside-dir", "busydir", "unwritable-dir"
    # and copy the files there, and set their permissions, etc
    # this isn't used but would be useful for testing calling dtrx on an archive
    # that's not in the current directory
    directory=None,
    # commands to run before test
    prerun=None,
    # text to input to the command through stdin
    # it's single letters used to select the appropriate action
    # (like extract _H_ere etc.)
    input=None,
    # commands to run after test
    posttest=None,
    # commands to clean up after or before running tests
    cleanup=None,
    # the correct command
    # the result of running this command is compared with dtrx
    baseline=None,
    # the correct output (file structure) dtrx should output while executing
    # as reported by the `find` bash command
    # TODO: rename to expected_output
    output=None,
    # if the command should error
    # TODO: rename to should_error
    error=False,
    # check that dtrx's output contains these strings
    grep=None,
    # check that dtrx's output doesn't contain these strings
    antigrep=None,
):

    options = options.split()
    filenames = filenames.split()

    if grep is None:
        grep = []
    if antigrep is None:
        antigrep = []

    if isinstance(grep, str):
        grep = [grep]
    if isinstance(antigrep, str):
        antigrep = [antigrep]

    grep = [pattern.replace(" ", "\\s+") for pattern in grep]
    antigrep = [pattern.replace(" ", "\\s+") for pattern in antigrep]

    if input is not None and not input.endswith("\n"):
        input += "\n"

    should_error = error
    expected_output = output

    print("test parameters after defaults:")
    pprint(vars())
    print()

    test_dir = (tmp_path / "test").absolute()
    baseline_dir = (tmp_path / "baseline").absolute()
    test_dir.mkdir()
    baseline_dir.mkdir()

    for filename in filenames:
        original = TEST_FILES_PATH / filename
        copyfile(original, test_dir / filename)
        copyfile(original, baseline_dir / filename)

    os.chdir(test_dir)
    result = run_command([DTRX_SCRIPT] + options + filenames, input, prerun)

    assert bool(result.returncode) == should_error
    if expected_output is not None:
        assert result.stdout.strip() == expected_output.strip()

    stdout_and_stderr = result.stdout + result.stderr
    for pattern in grep:
        assert re.search(pattern, stdout_and_stderr, re.MULTILINE) is not None
    for pattern in antigrep:
        assert re.search(pattern, stdout_and_stderr, re.MULTILINE) is None

    actual_files = list_all_files(test_dir)
    print("files after running dtrx:")
    pprint(actual_files)

    # if posttest is None, this just opens and closes a shell.
    # pass the posttest paramater as stdin to an `sh` command
    # in other words, instead of run()ing the command, get subprocess.run
    # to type it in, letter by letter
    # TODO: change this to just build a full command.
    assert run_command(SHELL_CMD + [""], input=posttest).returncode == 0

    if baseline is None:
        return

    os.chdir(baseline_dir)
    baseline_result = run_command(SHELL_CMD + filenames, input=baseline, prerun=prerun)

    print("running baseline command:", baseline)
    print("baseline stdout:", baseline_result.stdout)
    print("baseline stderr:", baseline_result.stderr)
    # assert baseline_result.returncode == 0  # commented out because baseline may fail

    expected_files = list_all_files(baseline_dir)
    print("files after running baseline:")
    pprint(expected_files)
    assert actual_files == expected_files


def test_basic_tar(tmp_path):
    call_test(tmp_path, filenames="test-1.23.tar", baseline="tar -xf $1\n")


def test_basic_targz(tmp_path):
    call_test(tmp_path, filenames="test-1.23.tar.gz", baseline="tar -zxf $1\n")


def test_basic_tarbz2(tmp_path):
    call_test(
        tmp_path,
        filenames="test-1.23.tar.bz2",
        baseline="mkdir test-1.23\ncd test-1.23\ntar -jxf ../$1\n",
    )


def test_basic_tarlrz(tmp_path):
    call_test(
        tmp_path, filenames="test-1.23.tar.lrz", baseline="lrzcat $1 | tar -xf -\n"
    )


def test_basic_zip(tmp_path):
    call_test(
        tmp_path,
        filenames="test-1.23.zip",
        baseline="mkdir test-1.23\ncd test-1.23\nunzip -q ../$1\n",
    )


def test_basic_lzh(tmp_path):
    call_test(
        tmp_path,
        filenames="test-1.23.lzh",
        baseline="mkdir test-1.23\ncd test-1.23\nlha xq ../$1\n",
    )


def test_basic_deb(tmp_path):
    call_test(
        tmp_path,
        filenames="test-1.23_all.deb",
        baseline="mkdir test-1.23\ncd test-1.23\nar p ../$1 data.tar.gz | tar -zx\n",
    )


def test_deb_with_LZMA_compression(tmp_path):
    call_test(
        tmp_path,
        filenames="test-2_all.deb",
        baseline="mkdir test-2\ncd test-2\nar p ../$1 data.tar.lzma | lzcat | tar -x\n",
    )


def test_basic_gem(tmp_path):
    call_test(
        tmp_path,
        filenames="test-1.23.gem",
        baseline="mkdir test-1.23\ncd test-1.23\ntar -xOf ../$1 data.tar.gz | tar -zx\n",
    )


def test_basic_7z(tmp_path):
    call_test(tmp_path, filenames="test-1.23.7z", baseline="7z x $1\n")


def test_basic_lzma(tmp_path):
    call_test(tmp_path, filenames="test-1.23.tar.lzma", baseline="lzcat $1 | tar -x\n")


def test_basic_cpio(tmp_path):
    call_test(
        tmp_path,
        filenames="test-1.23.cpio",
        baseline="cpio -i --make-directories <$1\n",
        antigrep="blocks?",
    )


def test_basic_rar(tmp_path):
    call_test(
        tmp_path,
        filenames="test-1.23.rar",
        baseline="mkdir test-1.23\ncd test-1.23\nunar -D ../$1 || unrar x ../$1\n",
    )


def test_basic_arj(tmp_path):
    call_test(
        tmp_path,
        filenames="test-1.23.arj",
        baseline="mkdir test-1.23\ncd test-1.23\narj x -y ../$1\n",
    )


def test_deb_metadata(tmp_path):
    call_test(
        tmp_path,
        filenames="test-1.23_all.deb",
        options="--metadata",
        baseline="mkdir test-1.23\ncd test-1.23\nar p ../$1 control.tar.gz | tar -zx\n",
    )


def test_gem_metadata(tmp_path):
    call_test(
        tmp_path,
        filenames="test-1.23.gem",
        options="-m",
        baseline="tar -xOf $1 metadata.gz | zcat > test-1.23.gem-metadata.txt\n",
        cleanup="rm -f test-1.23.gem-metadata.txt",
        posttest='exec [ "$(cat test-1.23.gem-metadata.txt)" = "hi" ]\n',
    )


def test_recursion_and_permissions(tmp_path):
    call_test(
        tmp_path,
        filenames="test-recursive-badperms.tar.bz2",
        options="-n -r",
        baseline='extract() {\n  mkdir "$1"\n  cd "$1"\n  tar "-${3}xf" "../$2"\n}\nextract test-recursive-badperms "$1" j\nextract test-badperms test-badperms.tar\nchmod 700 testdir\n',
        posttest='exec [ "$(cat test-recursive-badperms/test-badperms/testdir/testfile)" = \\\n       "hey" ]\n',
    )


def test_decompressing_gz_not_interactive(tmp_path):
    call_test(
        tmp_path,
        directory="inside-dir",
        filenames="test-text.gz",
        options="",
        antigrep=".",
        baseline="zcat $1 >test-text\n",
        posttest='exec [ "$(cat test-text)" = "hi" ]\n',
    )


def test_decompressing_bz2_not_interactive(tmp_path):
    call_test(
        tmp_path,
        directory="inside-dir",
        filenames="test-text.bz2",
        options="",
        antigrep=".",
        baseline="bzcat $1 >test-text\n",
        posttest='exec [ "$(cat test-text)" = "hi" ]\n',
    )


def test_decompressing_xz_not_interactive(tmp_path):
    call_test(
        tmp_path,
        directory="inside-dir",
        filenames="test-text.xz",
        options="",
        antigrep=".",
        baseline="xzcat $1 >test-text\n",
        posttest='exec [ "$(cat test-text)" = "hi" ]\n',
    )


def test_decompressing_lrzip_not_interactive(tmp_path):
    call_test(
        tmp_path,
        directory="inside-dir",
        filenames="test-text.lrz",
        options="",
        antigrep=".",
        baseline="lrzcat $1 >test-text\n",
        posttest='exec [ "$(cat test-text)" = "hi" ]\n',
    )


def test_decompressing_lzip_not_interactive(tmp_path):
    call_test(
        tmp_path,
        directory="inside-dir",
        filenames="test-text.lz",
        options="",
        antigrep=".",
        baseline="lzip -cd <$1 >test-text\n",
        posttest='exec [ "$(cat test-text)" = "hi" ]\n',
    )


def test_decompression_with_recursive_flag(tmp_path):
    call_test(
        tmp_path,
        directory="inside-dir",
        filenames="test-text.gz",
        options="-n -r",
        baseline="zcat $1 >test-text\n",
    )


def test_decompression_with_recursive_and_flat_flags(tmp_path):
    call_test(
        tmp_path,
        directory="inside-dir",
        filenames="test-text.gz",
        options="-n -fr",
        baseline="zcat $1 >test-text\n",
    )


def test_overwrite_protection(tmp_path):
    call_test(
        tmp_path,
        filenames="test-1.23.tar.bz2",
        baseline="mkdir test-1.23.1\ncd test-1.23.1\ntar -jxf ../$1\n",
        prerun="mkdir test-1.23\n",
    )


def test_overwrite_option(tmp_path):
    call_test(
        tmp_path,
        filenames="test-1.23.tar.bz2",
        options="-n -o",
        baseline="cd test-1.23\ntar -jxf ../$1\n",
        prerun="mkdir test-1.23\n",
    )


def test_flat_option(tmp_path):
    call_test(
        tmp_path,
        directory="inside-dir",
        filenames="test-1.23.tar.bz2",
        options="-n -f",
        baseline="tar -jxf $1\n",
    )


def test_flat_recursion_and_permissions(tmp_path):
    call_test(
        tmp_path,
        directory="inside-dir",
        filenames="test-recursive-badperms.tar.bz2",
        options="-n -fr",
        baseline="tar -jxf $1\ntar -xf test-badperms.tar\nchmod 700 testdir\n",
        posttest='exec [ "$(cat testdir/testfile)" = "hey" ]\n',
    )


def test_no_files(tmp_path):
    call_test(tmp_path, error=True, grep="[Uu]sage")


def test_bad_file(tmp_path):
    call_test(tmp_path, error=True, filenames="nonexistent-file.tar")


def test_not_an_archive(tmp_path):
    call_test(tmp_path, error=True, filenames="tests.yml")


def test_bad_options(tmp_path):
    call_test(
        tmp_path,
        options="-n --nonexistent-option",
        filenames="test-1.23.tar",
        error=True,
    )


def test_version_flag(tmp_path):
    call_test(
        tmp_path,
        options="-n --version",
        grep="ersion \\d+\\.\\d+",
        filenames="test-1.23.tar",
        baseline="exit 0\n",
    )


def test_one_good_archive_of_many(tmp_path):
    call_test(
        tmp_path,
        filenames="tests.yml test-1.23.tar nonexistent-file.tar",
        error=True,
        baseline="tar -xf $2\n",
    )


def test_silence(tmp_path):
    call_test(
        tmp_path, filenames="tests.yml", options="-n -qq", error=True, antigrep="."
    )


def test_cant_write_to_directory(tmp_path):
    call_test(
        tmp_path,
        directory="inside-dir",
        filenames="test-1.23.tar",
        error=True,
        grep="ERROR",
        antigrep="Traceback",
        prerun="chmod 500 .\n",
    )


def test_list_contents_of_one_file(tmp_path):
    call_test(
        tmp_path,
        options="-n -l",
        filenames="test-1.23.tar",
        output="test-1.23/\ntest-1.23/1/\ntest-1.23/1/2/\ntest-1.23/1/2/3\ntest-1.23/a/\ntest-1.23/a/b\ntest-1.23/foobar\n",
    )


def test_list_contents_of_LZH(tmp_path):
    call_test(
        tmp_path,
        options="-n -l",
        filenames="test-1.23.lzh",
        output="1/\n1/2/\n1/2/3\na/\na/b\nfoobar\n",
    )


def test_list_contents_of_arj(tmp_path):
    call_test(
        tmp_path,
        options="-n -l",
        filenames="test-1.23.arj",
        output="a/b\n1/2/3\nfoobar\n",
    )


def test_list_contents_of_cpio(tmp_path):
    call_test(
        tmp_path,
        options="-n -l",
        filenames="test-1.23.cpio",
        grep="^test-1\\.23/1/2/3$",
        antigrep="blocks?",
    )


def test_list_contents_of_multiple_files(tmp_path):
    call_test(
        tmp_path,
        options="-n --table",
        filenames="test-1.23_all.deb test-1.23.zip",
        output="test-1.23_all.deb:\n1/\n1/2/\n1/2/3\na/\na/b\nfoobar\n\ntest-1.23.zip:\n1/2/3\na/b\nfoobar\n",
    )


def test_list_contents_of_compressed_file(tmp_path):
    call_test(tmp_path, options="-n -t", filenames="test-text.gz", output="test-text")


def test_default_behavior_with_one_directory_gz(tmp_path):
    call_test(
        tmp_path,
        options="-n",
        filenames="test-onedir.tar.gz",
        baseline="mkdir test-onedir\ncd test-onedir\ntar -zxf ../$1\n",
    )


def test_one_directory_extracted_inside_another_interactively_gz(tmp_path):
    call_test(
        tmp_path,
        options="",
        filenames="test-onedir.tar.gz",
        grep="one directory",
        input="i",
        baseline="mkdir test-onedir\ncd test-onedir\ntar -zxf ../$1\n",
    )


def test_one_directory_extracted_with_rename_interactively_gz(tmp_path):
    call_test(
        tmp_path,
        options="",
        filenames="test-onedir.tar.gz",
        input="r",
        baseline="tar -zxf $1\nmv test test-onedir\n",
    )


def test_one_directory_extracted_here_interactively_gz(tmp_path):
    call_test(
        tmp_path,
        options="",
        filenames="test-onedir.tar.gz",
        input="h",
        baseline="tar -zxf $1\n",
    )


def test_one_entry_policy_inside(tmp_path):
    call_test(
        tmp_path,
        options="--one=inside -n",
        filenames="test-onedir.tar.gz",
        baseline="mkdir test-onedir\ncd test-onedir\ntar -zxf ../$1\n",
    )


def test_one_entry_policy_rename(tmp_path):
    call_test(
        tmp_path,
        options="--one-entry=rename -n",
        filenames="test-onedir.tar.gz",
        baseline="tar -zxf $1\nmv test test-onedir\n",
    )


def test_one_entry_policy_here(tmp_path):
    call_test(
        tmp_path,
        options="--one=here -n",
        filenames="test-onedir.tar.gz",
        baseline="tar -zxf $1\n",
    )


def test_default_behavior_with_one_directory_bz2(tmp_path):
    call_test(
        tmp_path,
        options="-n",
        filenames="test-onedir.tar.gz",
        baseline="mkdir test-onedir\ncd test-onedir\ntar -zxf ../$1\n",
    )


def test_one_directory_extracted_inside_another_bz2(tmp_path):
    call_test(
        tmp_path,
        options="",
        filenames="test-onedir.tar.gz",
        input="i",
        baseline="mkdir test-onedir\ncd test-onedir\ntar -zxf ../$1\n",
    )


def test_one_directory_extracted_with_rename_bz2(tmp_path):
    call_test(
        tmp_path,
        options="",
        filenames="test-onedir.tar.gz",
        input="r",
        baseline="tar -zxf $1\nmv test test-onedir\n",
    )


def test_one_directory_extracted_here_bz2(tmp_path):
    call_test(
        tmp_path,
        options="",
        filenames="test-onedir.tar.gz",
        input="h",
        baseline="tar -zxf $1\n",
    )


def test_default_behavior_with_one_file(tmp_path):
    call_test(
        tmp_path,
        options="-n",
        filenames="test-onefile.tar.gz",
        baseline="mkdir test-onefile\ncd test-onefile\ntar -zxf ../$1\n",
    )


def test_one_file_extracted_inside_a_directory(tmp_path):
    call_test(
        tmp_path,
        options="",
        filenames="test-onefile.tar.gz",
        input="i",
        grep="one file",
        baseline="mkdir test-onefile\ncd test-onefile\ntar -zxf ../$1\n",
    )


def test_prompt_wording_with_one_file(tmp_path):
    call_test(
        tmp_path,
        options="",
        filenames="test-onefile.tar.gz",
        input="i",
        grep="file _I_nside",
    )


def test_one_file_extracted_with_rename_with_Expected_text(tmp_path):
    call_test(
        tmp_path,
        options="",
        filenames="test-onefile.tar.gz",
        input="r",
        grep="Expected: test-onefile",
        baseline="tar -zxOf $1 >test-onefile\n",
    )


def test_one_file_extracted_here_with_Actual_text(tmp_path):
    call_test(
        tmp_path,
        options="",
        filenames="test-onefile.tar.gz",
        input="h",
        grep="  Actual: test-text",
        baseline="tar -zxf $1\n",
    )


def test_bomb_with_preceding_dot_in_the_table(tmp_path):
    call_test(
        tmp_path,
        filenames="test-dot-first-bomb.tar.gz",
        options="",
        antigrep="one",
        baseline="mkdir test-dot-first-bomb\ncd test-dot-first-bomb\ntar -zxf ../$1\n",
    )


def test_one_directory_preceded_by_dot_in_the_table(tmp_path):
    call_test(
        tmp_path,
        filenames="test-dot-first-onedir.tar.gz",
        options="",
        grep="Actual: (./)?dir/",
        input="h",
        baseline="tar -zxf $1\n",
    )


def test_two_one_item_archives_with_different_answers(tmp_path):
    call_test(
        tmp_path,
        filenames="test-onedir.tar.gz test-onedir.tar.gz",
        options="",
        input="h\nr\n",
        baseline="tar -zxf $1\nmv test test-onedir\ntar -zxf $1\n",
    )


def test_interactive_recursion_always(tmp_path):
    call_test(
        tmp_path,
        filenames="test-recursive-badperms.tar.bz2 test-recursive-badperms.tar.bz2",
        options="",
        input="i\na\ni\n",
        baseline="extract() {\n  mkdir test-recursive-badperms$2\n  cd test-recursive-badperms$2\n  tar -jxf ../$1\n  mkdir test-badperms\n  cd test-badperms\n  tar -xf ../test-badperms.tar\n  chmod 700 testdir\n  cd ../..\n}\nextract $1\nextract $1 .1\n",
    )


def test_interactive_recursion_once(tmp_path):
    call_test(
        tmp_path,
        filenames="test-recursive-badperms.tar.bz2 test-recursive-badperms.tar.bz2",
        options="",
        input="i\no\ni\nn\n",
        baseline='extract() {\n  mkdir "$1"\n  cd "$1"\n  tar "-${3}xf" "../$2"\n}\nextract test-recursive-badperms "$1" j\nextract test-badperms test-badperms.tar\nchmod 700 testdir\ncd ../..\nextract test-recursive-badperms.1 "$1" j\n',
    )


def test_interactive_recursion_never(tmp_path):
    call_test(
        tmp_path,
        filenames="test-recursive-badperms.tar.bz2 test-recursive-badperms.tar.bz2",
        options="",
        input="i\nv\ni\n",
        baseline="extract() {\n  mkdir test-recursive-badperms$2\n  cd test-recursive-badperms$2\n  tar -jxf ../$1\n  cd ..\n}\nextract $1\nextract $1 .1\n",
    )


def test_recursion_in_subdirectories_here(tmp_path):
    call_test(
        tmp_path,
        filenames="test-deep-recursion.tar",
        options="",
        input="h\no\n",
        grep="contains 2 other archive file\\(s\\), out of 2 file\\(s\\)",
        baseline="tar -xf $1\ncd subdir\nzcat test-text.gz > test-text\ncd subsubdir\nzcat test-text.gz > test-text\n",
    )


def test_recursion_in_subdirectories_with_rename(tmp_path):
    call_test(
        tmp_path,
        filenames="test-deep-recursion.tar",
        options="",
        input="r\no\n",
        grep="contains 2",
        baseline="tar -xf $1\nmv subdir test-deep-recursion\ncd test-deep-recursion\nzcat test-text.gz > test-text\ncd subsubdir\nzcat test-text.gz > test-text\n",
    )


def test_recursion_in_subdirectories_inside_new_dir(tmp_path):
    call_test(
        tmp_path,
        filenames="test-deep-recursion.tar",
        options="",
        input="i\no\n",
        grep="contains 2",
        baseline="mkdir test-deep-recursion\ncd test-deep-recursion\ntar -xf ../$1\ncd subdir\nzcat test-text.gz > test-text\ncd subsubdir\nzcat test-text.gz > test-text\n",
    )


def test_no_such_file_error(tmp_path):
    call_test(
        tmp_path,
        filenames="nonexistent-file.tar.gz",
        error=True,
        grep="[Nn]o such file",
    )


def test_no_such_file_error_with_no_extension(tmp_path):
    call_test(
        tmp_path, filenames="nonexistent-file", error=True, grep="[Nn]o such file"
    )


def test_try_to_extract_a_directory_error(tmp_path):
    call_test(
        tmp_path,
        filenames="test-directory",
        prerun="mkdir test-directory",
        error=True,
        grep="cannot work with a directory",
    )


def test_permission_denied_error(tmp_path):
    call_test(
        tmp_path,
        filenames="unreadable-file.tar.gz",
        prerun="touch unreadable-file.tar.gz\nchmod 000 unreadable-file.tar.gz\n",
        cleanup="rm -f unreadable-file.tar.gz",
        error=True,
        grep="[Pp]ermission denied",
    )


def test_permission_denied_no_pipe_file_error(tmp_path):
    call_test(
        tmp_path,
        filenames="unreadable-file.zip",
        prerun="touch unreadable-file.zip\nchmod 000 unreadable-file.zip\n",
        cleanup="rm -f unreadable-file.zip",
        error=True,
        grep="[Pp]ermission denied",
    )


def test_bad_file_error(tmp_path):
    call_test(
        tmp_path,
        filenames="bogus-file.tar.gz",
        prerun="touch bogus-file.tar.gz\n",
        cleanup="rm -f bogus-file.tar.gz",
        error=True,
        grep="returned status code [^0]",
    )


def test_try_to_extract_in_unwritable_directory(tmp_path):
    call_test(
        tmp_path,
        directory="unwritable-dir",
        filenames="test-1.23.tar.gz",
        prerun="chmod 500 .",
        error=True,
        grep="cannot extract here: [Pp]ermission denied",
    )


def test_recursive_listing_is_a_no_op(tmp_path):
    call_test(
        tmp_path,
        options="-rl",
        filenames="test-recursive-badperms.tar.bz2",
        grep="test-badperms.tar",
        antigrep="testdir/",
    )


def test_graceful_coping_when_many_extraction_directories_are_taken(tmp_path):
    call_test(
        tmp_path,
        directory="busydir",
        prerun="mkdir test-1.23\nfor i in $(seq 1 10); do mkdir test-1.23.$i; done\n",
        filenames="test-1.23.tar.gz",
        grep="WARNING: extracting",
    )


def test_graceful_coping_when_many_decompression_targets_are_taken(tmp_path):
    call_test(
        tmp_path,
        directory="busydir",
        prerun="touch test-text\nfor i in $(seq 1 10); do touch test-text.$i; done\n",
        filenames="test-text.gz",
        grep="WARNING: extracting",
    )


def test_output_filenames_with_verbose_flag(tmp_path):
    call_test(
        tmp_path,
        options="-v -n",
        filenames="test-onedir.tar.gz test-text.gz",
        output="test-onedir.tar.gz:\ntest-onedir/\ntest-onedir/test/\ntest-onedir/test/foobar\ntest-onedir/test/quux\n\ntest-text.gz:\ntest-text\n",
    )


def test_output_filenames_with_verbose_and_flat_flags(tmp_path):
    call_test(
        tmp_path,
        options="-nvf",
        directory="busydir",
        filenames="test-onedir.tar.gz",
        output="test/\ntest/foobar\ntest/quux\n",
    )


def test_list_recursive_archives(tmp_path):
    call_test(
        tmp_path,
        options="",
        filenames="test-deep-recursion.tar",
        input="r\nl\nn\n",
        grep="^test-deep-recursion/subsubdir/test-text\\.gz$",
    )


def test_partly_failed_extraction(tmp_path):
    call_test(
        tmp_path,
        options="-n",
        filenames="test-tar-with-node.tar.gz",
        baseline="mkdir test-tar-with-node\ncd test-tar-with-node\ntar -zxf ../$1\n",
        grep="Cannot mknod",
    )


def test_flat_extraction_of_one_file_archive(tmp_path):
    call_test(
        tmp_path,
        directory="inside-dir",
        options="-f",
        filenames="test-onefile.tar.gz",
        baseline="tar -zxf $1",
        antigrep="contains",
    )


def test_test_recursive_extraction_of_one_archive(tmp_path):
    call_test(
        tmp_path,
        directory="inside-dir",
        options="",
        filenames="test-one-archive.tar.gz",
        baseline="tar -zxf $1\nzcat test-text.gz >test-text\n",
        input="h\no\n",
    )


def test_extracting_empty_archive(tmp_path):
    call_test(
        tmp_path, filenames="test-empty.tar.bz2", options="", baseline="", antigrep="."
    )


def test_listing_empty_archive(tmp_path):
    call_test(tmp_path, filenames="test-empty.tar.bz2", options="-l", antigrep=".")


def test_recursive_archive_without_prompt(tmp_path):
    call_test(
        tmp_path,
        filenames="test-recursive-no-prompt.tar.bz2",
        options="",
        baseline="mkdir test-recursive-no-prompt\ncd test-recursive-no-prompt\ntar -jxf ../$1\n",
        antigrep=".",
    )


# def test_extracting_file_with_bad_extension(tmp_path):
#     call_test(
#         tmp_path,
#         filenames="test-1.23.bin",
#         prerun="mv ${1}test-1.23.tar.gz ${1}test-1.23.bin",
#         cleanup="rm -f ${1}test-1.23.bin",
#         baseline="tar -zxf $1\n",
#     )


# def test_extracting_file_with_misleading_extension(tmp_path):
#     call_test(
#         tmp_path,
#         filenames="trickery.tar.gz",
#         prerun="cp ${1}test-1.23.zip ${1}trickery.tar.gz",
#         cleanup="rm -f ${1}trickery.tar.gz",
#         antigrep=".",
#         baseline="mkdir trickery\ncd trickery\nunzip -q ../$1\n",
#     )


# def test_listing_file_with_misleading_extension(tmp_path):
#     call_test(
#         tmp_path,
#         options="-l",
#         filenames="trickery.tar.gz",
#         prerun="cp ${1}test-1.23.zip ${1}trickery.tar.gz",
#         cleanup="rm -f ${1}trickery.tar.gz",
#         grep="^1/2/3$",
#         antigrep="^dtrx:",
#     )


# def test_listing_multiple_files_with_misleading_extensions(tmp_path):
#     call_test(
#         tmp_path,
#         options="-l",
#         filenames="trickery.tar.gz trickery.tar.gz",
#         prerun="cp ${1}test-1.23.zip ${1}trickery.tar.gz",
#         cleanup="rm -f ${1}trickery.tar.gz",
#         output="trickery.tar.gz:\n1/2/3\na/b\nfoobar\n\ntrickery.tar.gz:\n1/2/3\na/b\nfoobar\n",
#     )


# def test_non_archive_error(tmp_path):
#     call_test(
#         tmp_path, filenames="/dev/null", error=True, grep="not a known archive type"
#     )
