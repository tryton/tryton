# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import decimal
import importlib
import os
import sys
import time
import warnings
from email import charset

import __main__
from lxml import etree, objectify

__version__ = "7.6.16"
__series__ = '.'.join(__version__.split('.')[:2])

if not os.environ.get('TRYTOND_APPNAME'):
    os.environ['TRYTOND_APPNAME'] = os.path.basename(
        getattr(__main__, '__file__', 'trytond'))
if not os.environ.get('TRYTOND_TZ'):
    os.environ['TRYTOND_TZ'] = os.environ.get('TZ') or 'UTC'
os.environ['TZ'] = 'UTC'
if hasattr(time, 'tzset'):
    time.tzset()

if time.tzname[0] != 'UTC':
    warnings.warn('Timezone must be set to UTC instead of %s' % time.tzname[0])

# set email encoding for utf-8 to 'quoted-printable'
charset.add_charset('utf-8', charset.QP, charset.QP)

# prevent XML vulnerabilities by default
etree.set_default_parser(etree.XMLParser(resolve_entities=False))
objectify.set_default_parser(objectify.makeparser(resolve_entities=False))

decimal.DefaultContext.prec = int(os.environ.get('TRYTOND_DECIMAL_PREC', 28))


class _RequestPatchFinder:
    def find_spec(self, fullname, path, target=None):
        if fullname != 'requests.utils':
            return
        sys.meta_path.remove(self)
        spec = importlib.util.find_spec(fullname)
        loader = spec.loader
        original_exec = loader.exec_module

        def exec_module(module):
            original_exec(module)
            self._patch_requests_utils(module)
        loader.exec_module = exec_module
        return spec

    @staticmethod
    def _patch_requests_utils(module):
        def default_user_agent(name="Tryton"):
            return f"{name}/{__version__}"
        module.default_user_agent = default_user_agent


sys.meta_path.insert(0, _RequestPatchFinder())
