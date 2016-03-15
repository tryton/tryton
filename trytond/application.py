# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from trytond.wsgi import app

__all__ = ['app']

Pool.start()
import trytond.protocols.dispatcher
