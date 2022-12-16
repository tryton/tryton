# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import os
import imp
import gettext

from tryton.config import get_config_dir, CURRENT_DIR

__all__ = ['MODULES', 'register']

_ = gettext.gettext

MODULES = []


def register():
    global MODULES
    paths = [
        os.path.join(get_config_dir(), 'plugins'),
        os.path.join(CURRENT_DIR, 'plugins'),
        ]
    paths = list(filter(os.path.isdir, paths))

    imported = set()
    for path in paths:
        for plugin in os.listdir(path):
            module = os.path.splitext(plugin)[0]
            if module == '__init__' or module in imported:
                continue
            try:
                module = imp.load_module(module, *imp.find_module(module,
                        [path]))
                MODULES.append(module)
            except ImportError:
                continue
            else:
                imported.add(module.__name__)
