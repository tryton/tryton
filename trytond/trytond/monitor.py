#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import sys
import os
import subprocess
from threading import Lock
from trytond.modules import get_module_list

_lock = Lock()
_times = {}
_modules = None

def _modified(path):
    global _times
    global _lock
    _lock.acquire()
    try:
        try:
            if not os.path.isfile(path):
                return path in _times

            mtime = os.stat(path).st_mtime
            if path not in _times:
                _times[path] = mtime

            if mtime != _times[path]:
                _times[path] = mtime
                return True
        except:
            return True
    finally:
        _lock.release()
    return False

def monitor():
    '''
    Monitor module files for change

    :return: True if at least one file has changed
    '''
    global _modules
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
    if _modules is None:
        _modules = modules
    for module in modules.difference(_modules):
        if subprocess.call((sys.executable, '-c',
            'import trytond.modules.%s' % module)):
            modified = False
            break
        modified = True
    _modules = modules
    return modified
