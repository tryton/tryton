#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from .connection import *
from .res import *


def register():
    Pool.register(
        Connection,
        User,
        module='ldap_authentication', type_='model')
