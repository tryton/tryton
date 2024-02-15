# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import os
import time
import warnings
from email import charset

import __main__
from lxml import etree, objectify

__version__ = "6.8.13"

os.environ.setdefault(
    'TRYTOND_APPNAME',
    os.path.basename(getattr(__main__, '__file__', 'trytond')))
os.environ.setdefault('TRYTOND_TZ', os.environ.get('TZ', 'UTC'))
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
