#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

from .field import SQLType
from .char import Char


class Text(Char):
    '''
    Define a text field (``unicode``).
    '''
    _type = 'text'

    def sql_type(self):
        return SQLType('TEXT', 'TEXT')
