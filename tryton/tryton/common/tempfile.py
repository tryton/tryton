# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import atexit
import os
import shutil
import tempfile

_files, _directories = [], []


def mkstemp(*args, **kwargs):
    fileno, fname = tempfile.mkstemp(*args, **kwargs)
    _files.append(fname)
    return fileno, fname


def mkdtemp(*args, **kwargs):
    dname = tempfile.mkdtemp(*args, **kwargs)
    _directories.append(dname)
    return dname


@atexit.register
def clean():
    for fname in _files:
        try:
            os.remove(fname)
        except (FileNotFoundError, PermissionError):
            pass
    _files.clear()

    for dname in _directories:
        shutil.rmtree(dname, ignore_errors=True)
    _directories.clear()
