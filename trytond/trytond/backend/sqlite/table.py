# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import logging
import re
import warnings
from weakref import WeakKeyDictionary

from trytond.backend.table import (
    IndexTranslatorInterface, TableHandlerInterface)
from trytond.transaction import Transaction

from .database import sqlite

__all__ = ['TableHandler']

logger = logging.getLogger(__name__)
VARCHAR_SIZE_RE = re.compile(r'VARCHAR\(([0-9]+)\)')


def _escape_identifier(name):
    return '"%s"' % name.replace('"', '""')


class TableHandler(TableHandlerInterface):
    __handlers = WeakKeyDictionary()
    index_translators = []

    def _init(self, model, history=False):
        super()._init(model, history=history)
        self.__columns = None
        self.__indexes = None
        self._model = model

        cursor = Transaction().connection.cursor()
        # Create new table if necessary
        if not self.table_exist(self.table_name):
            if not self.history:
                cursor.execute('CREATE TABLE %s '
                    '(id INTEGER PRIMARY KEY AUTOINCREMENT)'
                    % _escape_identifier(self.table_name))
            else:
                cursor.execute('CREATE TABLE %s '
                    '(__id INTEGER PRIMARY KEY AUTOINCREMENT, '
                    'id INTEGER)' % _escape_identifier(self.table_name))

        self._update_definitions()

    @classmethod
    def table_exist(cls, table_name):
        cursor = Transaction().connection.cursor()
        cursor.execute("SELECT sql FROM sqlite_master "
            "WHERE type = 'table' AND name = ?",
            (table_name,))
        res = cursor.fetchone()
        if not res:
            return False
        return True

    @classmethod
    def table_rename(cls, old_name, new_name):
        cursor = Transaction().connection.cursor()
        if (cls.table_exist(old_name)
                and not cls.table_exist(new_name)):
            cursor.execute('ALTER TABLE %s RENAME TO %s'
                % (_escape_identifier(old_name), _escape_identifier(new_name)))
        # Rename history table
        old_history = old_name + "__history"
        new_history = new_name + "__history"
        if (cls.table_exist(old_history)
                and not cls.table_exist(new_history)):
            cursor.execute('ALTER TABLE %s RENAME TO %s'
                % (_escape_identifier(old_history),
                    _escape_identifier(new_history)))

    def column_exist(self, column_name):
        return column_name in self._columns

    def _recreate_table(self, update_columns=None, drop_columns=None):
        if update_columns is None:
            update_columns = {}
        if drop_columns is None:
            drop_columns = []
        transaction = Transaction()
        database = transaction.database
        cursor = transaction.connection.cursor()
        temp_table = '__temp_%s' % self.table_name
        temp_columns = dict(self._columns)
        self.table_rename(self.table_name, temp_table)
        self._init(self._model, history=self.history)
        columns, old_columns = [], []
        for name, values in temp_columns.items():
            if name in drop_columns:
                continue
            typname = update_columns.get(name, {}).get(
                'typname', values['typname'])
            size = update_columns.get(name, {}).get('size', values['size'])
            name = update_columns.get(name, {}).get('name', name)
            self._add_raw_column(
                name, database.sql_type(typname), field_size=size)
            columns.append(name)
            old_columns.append(name)
        cursor.execute(('INSERT INTO %s ('
                + ','.join(_escape_identifier(x) for x in columns)
                + ') SELECT '
                + ','.join(_escape_identifier(x) for x in old_columns)
                + ' FROM %s') % (
                _escape_identifier(self.table_name),
                _escape_identifier(temp_table)))
        cursor.execute('DROP TABLE %s' % _escape_identifier(temp_table))
        self._update_definitions()

    def column_rename(self, old_name, new_name):
        cursor = Transaction().connection.cursor()
        if self.column_exist(old_name):
            if not self.column_exist(new_name):
                if sqlite.sqlite_version_info >= (3, 25, 0):
                    cursor.execute('ALTER TABLE %s RENAME COLUMN %s TO %s' % (
                            _escape_identifier(self.table_name),
                            _escape_identifier(old_name),
                            _escape_identifier(new_name)))
                    self._update_definitions(columns=True)
                else:
                    self._recreate_table({old_name: {'name': new_name}})
            else:
                logger.warning(
                    'Unable to rename column %s on table %s to %s.',
                    old_name, self.table_name, new_name)

    @property
    def _columns(self):
        if self.__columns is None:
            cursor = Transaction().connection.cursor()
            cursor.execute('PRAGMA table_info("' + self.table_name + '")')
            self.__columns = {}
            for _, column, type_, notnull, hasdef, _ in cursor:
                column = re.sub(r'^\"|\"$', '', column)
                match = re.match(r'(\w+)(\((.*?)\))?', type_)
                if match:
                    typname = match.group(1).upper()
                    size = match.group(3) and int(match.group(3)) or 0
                else:
                    typname = type_.upper()
                    size = None
                self.__columns[column] = {
                    'notnull': notnull,
                    'hasdef': hasdef,
                    'size': size,
                    'typname': typname,
                }
        return self.__columns

    @property
    def _indexes(self):
        if self.__indexes is None:
            cursor = Transaction().connection.cursor()
            try:
                cursor.execute('PRAGMA index_list("' + self.table_name + '")')
            except IndexError:  # There is sometimes IndexError
                cursor.execute('PRAGMA index_list("' + self.table_name + '")')
            self.__indexes = [l[1] for l in cursor]
        return self.__indexes

    def _update_definitions(self, columns=True):
        if columns:
            self.__columns = None

    def alter_size(self, column_name, column_type):
        self._recreate_table({column_name: {'size': column_type}})

    def alter_type(self, column_name, column_type):
        self._recreate_table({column_name: {'typname': column_type}})

    def column_is_type(self, column_name, type_, *, size=-1):
        db_type = self._columns[column_name]['typname'].upper()

        database = Transaction().database
        base_type = database.sql_type(type_).base.upper()
        if base_type == 'VARCHAR' and (size is None or size >= 0):
            same_size = self._columns[column_name]['size'] == size
        else:
            same_size = True

        return base_type == db_type and same_size

    def db_default(self, column_name, value):
        warnings.warn('Unable to set default on column with SQLite backend')

    def add_column(self, column_name, sql_type, default=None, comment=''):
        database = Transaction().database
        column_type = database.sql_type(sql_type)
        match = VARCHAR_SIZE_RE.match(sql_type)
        field_size = int(match.group(1)) if match else None

        self._add_raw_column(column_name, column_type, default, field_size,
            comment)

    def _add_raw_column(self, column_name, column_type, default=None,
            field_size=None, string=''):
        if self.column_exist(column_name):
            base_type = column_type[0].upper()
            if base_type != self._columns[column_name]['typname']:
                if (self._columns[column_name]['typname'], base_type) in [
                        ('VARCHAR', 'TEXT'),
                        ('TEXT', 'VARCHAR'),
                        ('DATE', 'TIMESTAMP'),
                        ('INTEGER', 'FLOAT'),
                        ('INTEGER', 'NUMERIC'),
                        ('FLOAT', 'NUMERIC'),
                        ]:
                    self.alter_type(column_name, base_type)
                else:
                    logger.warning(
                        'Unable to migrate column %s on table %s '
                        'from %s to %s.',
                        column_name, self.table_name,
                        self._columns[column_name]['typname'], base_type)

            if (base_type == 'VARCHAR'
                    and self._columns[column_name]['typname'] == 'VARCHAR'):
                # Migrate size
                from_size = self._columns[column_name]['size']
                if field_size is None:
                    if from_size > 0:
                        self.alter_size(column_name, base_type)
                elif from_size == field_size:
                    pass
                elif from_size and from_size < field_size:
                    self.alter_size(column_name, column_type[1])
                else:
                    logger.warning(
                        'Unable to migrate column %s on table %s '
                        'from varchar(%s) to varchar(%s).',
                        column_name, self.table_name,
                        from_size if from_size and from_size > 0 else "",
                        field_size)
            return

        cursor = Transaction().connection.cursor()
        column_type = column_type[1]
        cursor.execute(('ALTER TABLE %s ADD COLUMN %s %s') % (
                _escape_identifier(self.table_name),
                _escape_identifier(column_name),
                column_type))

        if default:
            # check if table is non-empty:
            cursor.execute('SELECT 1 FROM %s limit 1'
                % _escape_identifier(self.table_name))
            if cursor.fetchone():
                # Populate column with default values:
                cursor.execute('UPDATE ' + _escape_identifier(self.table_name)
                    + ' SET ' + _escape_identifier(column_name) + ' = ?',
                    (default(),))

        self._update_definitions(columns=True)

    def add_fk(self, columns, reference, ref_columns=None, on_delete=None):
        warnings.warn('Unable to add foreign key with SQLite backend')

    def drop_fk(self, columns=None, ref_columns=None, table=None):
        warnings.warn('Unable to drop foreign key with SQLite backend')

    def not_null_action(self, column_name, action='add'):
        if not self.column_exist(column_name):
            return

        if action == 'add':
            warnings.warn('Unable to set not null with SQLite backend')
        elif action == 'remove':
            warnings.warn('Unable to remove not null with SQLite backend')
        else:
            raise Exception('Not null action not supported!')

    def add_constraint(self, ident, constraint):
        warnings.warn('Unable to add constraint with SQLite backend')

    def drop_constraint(self, ident, table=None):
        warnings.warn('Unable to drop constraint with SQLite backend')

    def set_indexes(self, indexes, concurrently=False):
        cursor = Transaction().connection.cursor()
        old = set(self._indexes)
        for index in indexes:
            translator = self.index_translator_for(index)
            if translator:
                name, query, params = translator.definition(index)
                name = '_'.join([self.table_name, name])
                name = 'idx_' + self.convert_name(name, reserved=len('idx_'))
                # SQLite does not support parameters for index creation
                if not params:
                    cursor.execute(
                        'CREATE INDEX IF NOT EXISTS %s ON %s %s' % (
                            _escape_identifier(name),
                            _escape_identifier(self.table_name),
                            query),
                        params)
                else:
                    warnings.warn("Can not create index with parameters")
                old.discard(name)
        for name in old:
            if name.startswith('idx_') or name.endswith('_index'):
                cursor.execute('DROP INDEX %s' % _escape_identifier(name))
        self.__indexes = None

    def drop_column(self, column_name):
        if not self.column_exist(column_name):
            return
        transaction = Transaction()
        cursor = transaction.connection.cursor()
        if sqlite.sqlite_version_info >= (3, 35, 0):
            cursor.execute('ALTER TABLE %s DROP COLUMN %s' % (
                    _escape_identifier(self.table_name),
                    _escape_identifier(column_name)))
            self._update_definitions(columns=True)
        else:
            self._recreate_table(drop_columns=[column_name])

    @classmethod
    def drop_table(cls, model, table, cascade=False):
        cursor = Transaction().connection.cursor()
        cursor.execute('DELETE from ir_model_data where model = ?',
            (model,))

        query = 'DROP TABLE %s' % _escape_identifier(table)
        if cascade:
            query = query + ' CASCADE'
        cursor.execute(query)


class IndexMixin:

    def __init_subclass__(cls):
        TableHandler.index_translators.append(cls)

    @classmethod
    def definition(cls, index):
        expr_template = '%(expression)s %(collate)s %(order)s'
        params = []
        expressions = []
        for expression, usage in index.expressions:
            expressions.append(expr_template %
                cls._get_expression_variables(expression, usage))
            params.extend(expression.params)

        where = ''
        if index.options.get('where'):
            where = 'WHERE %s' % index.options['where']
            params.extend(index.options['where'].params)

        query = '(%(expressions)s) %(where)s' % {
            'expressions': ','.join(expressions),
            'where': where,
            }
        name = cls._get_name(query, params)
        return name, query, params

    @classmethod
    def _get_expression_variables(cls, expression, usage):
        variables = {
            'expression': str(expression),
            'collate': '',
            'order': '',
            }
        if usage.options.get('collation'):
            variables['collate'] = 'COLLATE %s' % usage.options['collation']
        if usage.options.get('order'):
            order = usage.options['order'].upper()
            for predicate in ['NULLS FIRST', 'NULLS LAST']:
                if order.endswith(predicate):
                    order = order[:-len(predicate)]
            variables['order'] = order
        return variables


class IndexTranslator(IndexMixin, IndexTranslatorInterface):

    @classmethod
    def score(cls, index):
        supported_indexes_count = sum(
            int(u.__class__.__name__ in {'Equality', 'Range'})
            for _, u in index.expressions)
        return supported_indexes_count * 100
