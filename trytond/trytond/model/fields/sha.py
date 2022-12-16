#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import hashlib
from sql import Query, Expression

from ... import backend
from .field import SQLType
from .char import Char


class Sha(Char):
    '''
    Define a sha field (``unicode``) of len 40.
    '''
    _type = 'sha'

    def sql_format(self, value):
        if value is not None and not isinstance(value, (Query, Expression)):
            if isinstance(value, unicode):
                value = value.encode('utf-8')
            value = hashlib.sha1(value).hexdigest()
        return super(Sha, self).sql_format(value)

    def sql_type(self):
        db_type = backend.name()
        if db_type == 'mysql':
            return SQLType('CHAR', 'VARCHAR(40)')
        return SQLType('VARCHAR', 'VARCHAR(40)')
