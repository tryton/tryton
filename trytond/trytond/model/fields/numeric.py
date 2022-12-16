#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

from trytond.model.fields.float import Float


class Numeric(Float):
    '''
    Define a numeric field (``decimal``).
    '''
    _type = 'numeric'
