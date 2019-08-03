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

import os
import re
import struct
import subprocess
import sys
import tempfile
import termios
import yaml
from pathlib import Path
import pytest

TEST_YAML_FILE = Path("tests.yml")

# if tests are being run from the top level directory, cd into tests/
if Path('scripts/dtrx').exists() and Path('tests').exists():
    os.chdir('tests')
if not Path('../scripts/dtrx').exists() or not Path('../tests').exists():
    print("ERROR: Can't run tests from this directory!")
    sys.exit(2)

DTRX_SCRIPT = str(Path('../scripts/dtrx').absolute())
# -s stdin
#       Read commands from standard input (set automatically if no file arguments are present)
# -e errexit
#       exit immediately if any untested command fails
SHELL_CMD = ['sh', '-se']
ROOT_DIR = str(Path().absolute())

class ExtractorTestError(Exception):
    pass

class ExtractorTest:
    def __init__(self, test_data):
        defaults = {
            # options passed to `dtrx`
            "options": "-n",
            # which compressed files (from the tests directory) are used 
            # in this test
            "filenames": "",

            # TODO: I don't understand what this is used for
            # if present, it's one of
            # "busydir", "inside-dir", "unwritable-dir"
            "directory": None,

            # commands to run before test
            "prerun": None,
            # text to input to the command through stdin
            # it's single letters used to select the appropriate action
            # (like extract _H_ere etc.)
            "input": None,
            # commands to run after test
            "posttest": None,
            # commands to clean up after or before running tests
            "cleanup": None,

            # the correct command
            # the result of running this command is compared with dtrx
            "baseline": None,
            # the correct output (file structure) dtrx should output while executing
            "output": None,
            # if the command should error
            "error": False,

            # check that dtrx's output contains these strings
            "grep": [],
            # check that dtrx's output doesn't contain these strings
            "antigrep": [],
        }

        test = {**defaults, **test_data}

        test["options"] = test["options"].split()
        test["filenames"] = test["filenames"].split()

        for key in ("grep", "antigrep"):
            if isinstance(test[key], str):
                test[key] = [test[key]]

        if test["input"] is not None and not test["input"].endswith("\n"):
            test["input"] += "\n"

        for key in test:
            setattr(self, key, test[key])

    def start_proc(self, command, stdin=None, output=None):
        return subprocess.run(command, input=stdin, stdout=output, 
                              stderr=output, text=True).returncode

    def get_results(self, command, stdin=None):
        print("Output from {}:".format(' '.join(command)), file=self.outbuffer)
        self.outbuffer.flush()
        status = self.start_proc(command, stdin, self.outbuffer)
        find_command = subprocess.run(['find'], capture_output=True, text=True)
        files = find_command.stdout.split('\n')
        return status, set(files)

    def run_script(self, key):
        commands = getattr(self, key)
        if commands is not None:
            if self.directory is not None:
                directory_hint = '../'
            else:
                directory_hint = ''
            self.start_proc(SHELL_CMD + [directory_hint], commands)

    def get_shell_results(self):
        self.run_script('prerun')
        return self.get_results(SHELL_CMD + self.filenames, self.baseline)

    def get_extractor_results(self):
        self.run_script('prerun')
        return self.get_results([DTRX_SCRIPT] + self.options + self.filenames,
                                self.input)

    def get_posttest_result(self):
        if not self.posttest:
            return 0
        return self.start_proc(SHELL_CMD, self.posttest)

    def clean(self):
        self.run_script('cleanup')
        if self.directory is not None:
            target = os.path.join(ROOT_DIR, self.directory)
            extra_options = []
        else:
            target = ROOT_DIR
            extra_options = ['(', '(', '-type', 'd',
                             '!', '-name', 'CVS',
                             '!', '-name', '.svn', ')',
                             '-or', '-name', 'test-text',
                             '-or', '-name', 'test-onefile', ')']
        status = subprocess.call(['find', target,
                                  '-mindepth', '1', '-maxdepth', '1'] +
                                 extra_options +
                                 ['-exec', 'rm', '-rf', '{}', ';'])
        if status != 0:
            raise ExtractorTestError(f"cleanup exited with status code {status}")

    def show_report(self, status, message=None):
        self.outbuffer.seek(0, 0)
        sys.stdout.write(self.outbuffer.read(-1))
        if message is None:
            last_part = ''
        else:
            last_part = f': {message}'
        print(f"{status}: {self.name}{last_part}\n")
        return status.lower()

    def compare_results(self, actual):
        posttest_result = self.get_posttest_result()
        self.clean()
        status, expected = self.get_shell_results()
        self.clean()
        if expected != actual:
            print("Only in baseline results:", file=self.outbuffer)
            print('\n'.join(expected.difference(actual)), file=self.outbuffer)
            print("Only in actual results:", file=self.outbuffer)
            print('\n'.join(actual.difference(expected)), file=self.outbuffer)
            return self.show_report('FAILED')
        elif posttest_result != 0:
            print("Posttest gave status code", posttest_result, file=self.outbuffer)
            return self.show_report('FAILED')
        return 'passed'

    def have_error_mismatch(self, status):
        if self.error and (status == 0):
            return "dtrx did not return expected error"
        elif (not self.error) and (status != 0):
            return f"dtrx returned error code {status}"
        return None

    def grep_output(self, output):
        for pattern in self.grep:
            if not re.search(pattern.replace(' ', '\\s+'), output,
                             re.MULTILINE):
                return f"output did not match {pattern}"
        for pattern in self.antigrep:
            if re.search(pattern.replace(' ', '\\s+'), output, re.MULTILINE):
                return f"output matched antigrep {self.antigrep}"
        return None

    def check_output(self, output):
        if ((self.output is not None) and
            (self.output.strip() != output.strip())):
            return "output did not match provided text"
        return None

    def check_results(self):
        self.clean()
        status, actual = self.get_extractor_results()
        self.outbuffer.seek(0, 0)
        self.outbuffer.readline()
        output = self.outbuffer.read(-1)
        problem = (self.have_error_mismatch(status) or
                   self.check_output(output) or self.grep_output(output))
        if problem:
            return self.show_report('FAILED', problem)
        if self.baseline is not None:
            return self.compare_results(actual)
        else:
            self.clean()
            return 'passed'

    def run(self):
        with tempfile.TemporaryFile('w+') as outfile:
            self.outbuffer = outfile
            if self.directory is not None:
                os.mkdir(self.directory)
                os.chdir(self.directory)
            try:
                result = self.check_results()
            except ExtractorTestError as error:
                result = self.show_report('ERROR', error)
        if self.directory is not None:
            os.chdir(ROOT_DIR)
            subprocess.call(['chmod', '-R', '700', self.directory])
            subprocess.call(['rm', '-rf', self.directory])
        return result


def parse_tests(path_to_yaml):
    with open(path_to_yaml) as test_db:
        test_data = yaml.safe_load(test_db.read())

    tests = []
    for data in test_data:
        tests.append(data)

        if "directory" in data or ("baseline" not in data):
            continue
        # print(data)
        new_test_case = data.copy()
        new_test_case["name"] += " in .."
        new_test_case["directory"] = "inside-dir"
        new_test_case["filenames"] = " ".join(
            "../" + filename for filename in data.get("filenames", "").split()
        )
        tests.append(new_test_case)

    return tests

tests = parse_tests(TEST_YAML_FILE)

@pytest.mark.parametrize("test_data", tests)
def test_script(tmp_path, test_data):
    test = ExtractorTest(test_data)
    result = test.run()
    if result != "passed":
        from pprint import pprint
        print()
        print(f"FAILED TEST {test_data['name']}")
        pprint(test_data)
        pprint(test.__dict__)
        sys.exit(1)
    assert result == "passed"
