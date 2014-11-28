#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import os
import time
from email import Charset

from . import server

__all__ = ['server']

os.environ['TZ'] = 'UTC'
if hasattr(time, 'tzset'):
    time.tzset()

# set email encoding for utf-8 to 'quoted-printable'
Charset.add_charset('utf-8', Charset.QP, Charset.QP)
