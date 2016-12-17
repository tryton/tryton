# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import os
import time
from email import charset

__version__ = "3.8.10"

os.environ['TZ'] = 'UTC'
if hasattr(time, 'tzset'):
    time.tzset()

# set email encoding for utf-8 to 'quoted-printable'
charset.add_charset('utf-8', charset.QP, charset.QP)
