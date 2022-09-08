# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import hashlib
from weakref import WeakKeyDictionary

from trytond.transaction import Transaction


class TableHandlerInterface(object):
    '''
    Define generic interface to handle database table
    '''
    namedatalen = None
    __handlers = WeakKeyDictionary()

    def __new__(cls, model, history=False):
        transaction = Transaction()
        handlers = cls.__handlers.setdefault(transaction, {})
        key = (model.__name__, history)
        if key not in handlers:
            instance = handlers[key] = super().__new__(cls)
            instance._init(model, history=history)
        return handlers[key]

    def _init(self, model, history=False):
        '''
        :param model: the Model linked to the table
        :param module_name: the module name
        :param history: a boolean to define if it is a history table
        '''
        super(TableHandlerInterface, self).__init__()
        if history:
            self.table_name = model._table + '__history'
        else:
            self.table_name = model._table
        self.object_name = model.__name__
        if history:
            self.sequence_name = self.table_name + '___id_seq'
        else:
            self.sequence_name = self.table_name + '_id_seq'
        self.history = history

    @classmethod
    def table_exist(cls, table_name):
        raise NotImplementedError

    @classmethod
    def table_rename(cls, old_name, new_name):
        raise NotImplementedError

    def column_exist(self, column_name):
        raise NotImplementedError

    def column_rename(self, old_name, new_name):
        raise NotImplementedError

    def alter_size(self, column_name, column_type):
        raise NotImplementedError

    def alter_type(self, column_name, column_type):
        raise NotImplementedError

    def column_is_type(self, column_name, type_, *, size=-1):
        raise NotImplementedError

    def db_default(self, column_name, value):
        raise NotImplementedError

    def add_column(self, column_name, abstract_type, default=None, comment=''):
        raise NotImplementedError

    def add_fk(self, column_name, reference, on_delete=None):
        raise NotImplementedError

    def drop_fk(self, column_name, table=None):
        raise NotImplementedError

    def index_action(self, columns, action='add', where=None, table=None):
        raise NotImplementedError

    def not_null_action(self, column_name, action='add'):
        raise NotImplementedError

    def add_constraint(self, ident, constraint):
        raise NotImplementedError

    def drop_constraint(self, ident, table=None):
        raise NotImplementedError

    def drop_column(self, column_name):
        raise NotImplementedError

    @classmethod
    def drop_table(cls, model, table, cascade=False):
        raise NotImplementedError

    @classmethod
    def convert_name(cls, name):
        if cls.namedatalen and len(name) >= cls.namedatalen:
            if isinstance(name, str):
                name = name.encode('utf-8')
            name = hashlib.sha256(name).hexdigest()[:cls.namedatalen - 1]
        return name
