#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from tryton import common
import os
import sys
import imp
import gettext

_ = gettext.gettext

PLUGINS_PATH = os.path.dirname(__file__)
if not os.path.isdir(PLUGINS_PATH):
    # try for py2exe
    PLUGINS_PATH = os.path.join(os.path.abspath(os.path.normpath(
        os.path.dirname(sys.argv[0]))), 'plugins')
MODULES = []

if os.path.isdir(PLUGINS_PATH):
    for plugin in os.listdir(PLUGINS_PATH):
        if not os.path.isdir(os.path.join(PLUGINS_PATH, plugin)):
            continue
        module = os.path.splitext(plugin)[0]
        try:
            module = imp.load_module(module, *imp.find_module(module,
                    [PLUGINS_PATH]))
            MODULES.append(module)
        except ImportError, exception:
            continue


def execute(datas):
    result = {}

    for module in MODULES:
        for name, func in module.get_plugins(datas['model']):
            result[name] = func
    if not result:
        common.message(_('No available plugin for this resource!'))
        return False
    res = common.selection(_('Choose a Plugin'), result, alwaysask=True)
    if res:
        res[1](datas)
    return True
