# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import hashlib


class TableHandlerInterface(object):
    '''
    Define generic interface to handle database table
    '''
    namedatalen = None

    def __init__(self, model, module_name=None, history=False):
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
        self.module_name = module_name
        self.history = history

    @staticmethod
    def table_exist(table_name):
        '''
        Table exist

        :param table_name: the table name
        :return: a boolean
        '''
        raise NotImplementedError

    @staticmethod
    def table_rename(old_name, new_name):
        '''
        Rename table

        :param old_name: the old table name
        :param new_name: the new table name
        '''
        raise NotImplementedError

    def column_exist(self, column_name):
        '''
        Column exist

        :param column_name: the column name
        :return: a boolean
        '''
        raise NotImplementedError

    def column_rename(self, old_name, new_name):
        '''
        Rename column if exists

        :param old_name: the name of the existing column
        :param new_name: the new name of the column
        '''
        raise NotImplementedError

    def alter_size(self, column_name, column_type):
        '''
        Modify size of a column

        :param column_name: the column name
        :param column_type: the column definition
        '''
        raise NotImplementedError

    def alter_type(self, column_name, column_type):
        '''
        Modify type of a column

        :param column_name: the column name
        :param column_type: the column definition
        '''
        raise NotImplementedError

    def column_is_type(self, column_name, type_, *, size=-1):
        '''
        Return True if the column is of type type_

        :param column_name: the column name
        :param type_: the generic name of the type
        :param size: if `type` is VARCHAR you can specify its size.
                     Use a negative value to ignore the size check.
                     Defaults to -1
        :return: a boolean
        '''
        raise NotImplementedError

    def db_default(self, column_name, value):
        '''
        Set a default on a column

        :param column_name: the column name
        :param value: the default value
        '''
        raise NotImplementedError

    def add_column(self, column_name, abstract_type, default=None, comment=''):
        '''
        Add a column

        :param column_name: the column name
        :param abstract_type: the abstract type that will represent this column
        :param default: the method that return default value to use
        :param comment: An optional comment on the column
        '''
        raise NotImplementedError

    def add_fk(self, column_name, reference, on_delete=None):
        '''
        Add a foreign key

        :param column_name: the column name
        :param reference: the foreign table name
        :param on_delete: the "on delete" value
        '''
        raise NotImplementedError

    def drop_fk(self, column_name, table=None):
        '''
        Drop a foreign key

        :param column_name: the column name
        :param table: optional table name
        '''
        raise NotImplementedError

    def index_action(self, columns, action='add', where=None, table=None):
        '''
        Add/remove an index

        :param columns: the column or a list of columns/expressions
        :param action: 'add' or 'remove'
        :param where: predicate expression
        :param table: optional table name
        '''
        raise NotImplementedError

    def not_null_action(self, column_name, action='add'):
        '''
        Add/remove a "not null"

        :param column_name: the column name
        :param action: 'add' or 'remove'
        '''
        raise NotImplementedError

    def add_constraint(self, ident, constraint):
        '''
        Add a constraint

        :param ident: the name of the constraint
        :param constraint: the definition of the constraint
        '''
        raise NotImplementedError

    def drop_constraint(self, ident, table=None):
        '''
        Remove a constraint

        :param ident: the name of the constraint
        :param table: optional table name
        '''
        raise NotImplementedError

    def drop_column(self, column_name):
        '''
        Remove a column

        :param column_name: the column name
        '''
        raise NotImplementedError

    @staticmethod
    def drop_table(model, table, cascade=False):
        '''
        Remove a table and clean ir_model_data from the given model.

        :param model: the model name
        :param table: the table name
        :param cascade: a boolean to add "CASCADE" to the delete query
        '''
        raise NotImplementedError

    @classmethod
    def convert_name(cls, name):
        '''
        Convert data name in respect of namedatalen.

        :param name: the data name
        '''
        if cls.namedatalen and len(name) >= cls.namedatalen:
            if isinstance(name, str):
                name = name.encode('utf-8')
            name = hashlib.sha256(name).hexdigest()[:cls.namedatalen - 1]
        return name
