# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import os
import time
import logging
from email import charset

__version__ = "4.2.2"
logger = logging.getLogger(__name__)

os.environ['TZ'] = 'UTC'
if hasattr(time, 'tzset'):
    time.tzset()

if time.tzname[0] != 'UTC':
    logger.error('Timezone must be set to UTC instead of %s', time.tzname[0])

# set email encoding for utf-8 to 'quoted-printable'
charset.add_charset('utf-8', charset.QP, charset.QP)
