#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import os
import time

from . import server

__all__ = ['server']

os.environ['TZ'] = 'UTC'
if hasattr(time, 'tzset'):
    time.tzset()
