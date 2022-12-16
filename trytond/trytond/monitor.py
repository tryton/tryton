#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import sys
import os
import subprocess
from threading import Lock
from trytond.modules import get_module_list

_LOCK = Lock()
_TIMES = {}
_MODULES = None

def _modified(path):
    _LOCK.acquire()
    try:
        try:
            if not os.path.isfile(path):
                return path in _TIMES

            mtime = os.stat(path).st_mtime
            if path not in _TIMES:
                _TIMES[path] = mtime

            if mtime != _TIMES[path]:
                _TIMES[path] = mtime
                return True
        except Exception:
            return True
    finally:
        _LOCK.release()
    return False

def monitor():
    '''
    Monitor module files for change

    :return: True if at least one file has changed
    '''
    global _MODULES
    modified = False
    for module in sys.modules.keys():
        if not module.startswith('trytond.'):
            continue
        if not hasattr(sys.modules[module], '__file__'):
            continue
        path = getattr(sys.modules[module], '__file__')
        if not path:
            continue
        if os.path.splitext(path)[1] in ['.pyc', '.pyo', '.pyd']:
            path = path[:-1]
        if _modified(path):
            if subprocess.call((sys.executable, '-c', 'import %s' % module),
                    cwd=os.path.dirname(os.path.abspath(os.path.normpath(
                        os.path.join(__file__, '..'))))):
                modified = False
                break
            modified = True
    modules = set(get_module_list())
    if _MODULES is None:
        _MODULES = modules
    for module in modules.difference(_MODULES):
        if subprocess.call((sys.executable, '-c',
            'import trytond.modules.%s' % module)):
            modified = False
            break
        modified = True
    _MODULES = modules
    return modified
