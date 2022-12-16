# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.transaction import Transaction
from trytond.backend.table import TableHandlerInterface
import logging
import re
import warnings

__all__ = ['TableHandler']

logger = logging.getLogger(__name__)
VARCHAR_SIZE_RE = re.compile(r'VARCHAR\(([0-9]+)\)')


class TableHandler(TableHandlerInterface):
    def __init__(self, model, module_name=None, history=False):
        super(TableHandler, self).__init__(model,
                module_name=module_name, history=history)
        self._columns = {}
        self._constraints = []
        self._fk_deltypes = {}
        self._indexes = []
        self._model = model

        cursor = Transaction().connection.cursor()
        # Create new table if necessary
        if not self.table_exist(self.table_name):
            if not self.history:
                cursor.execute('CREATE TABLE "%s" '
                    '(id INTEGER PRIMARY KEY AUTOINCREMENT)'
                    % self.table_name)
            else:
                cursor.execute('CREATE TABLE "%s" '
                    '(__id INTEGER PRIMARY KEY AUTOINCREMENT, '
                    'id INTEGER)' % self.table_name)

        self._update_definitions()

    @staticmethod
    def table_exist(table_name):
        cursor = Transaction().connection.cursor()
        cursor.execute("SELECT sql FROM sqlite_master "
            "WHERE type = 'table' AND name = ?",
            (table_name,))
        res = cursor.fetchone()
        if not res:
            return False
        sql, = res

        # Migration from 1.6 add autoincrement

        if 'AUTOINCREMENT' not in sql.upper():
            temp_sql = sql.replace(table_name, '_temp_%s' % table_name)
            cursor.execute(temp_sql)
            cursor.execute('PRAGMA table_info("' + table_name + '")')
            columns = ['"%s"' % column for _, column, _, _, _, _
                    in cursor.fetchall()]
            cursor.execute(('INSERT INTO "_temp_%s" '
                    '(' + ','.join(columns) + ') '
                    'SELECT ' + ','.join(columns)
                    + ' FROM "%s"') % (table_name, table_name))
            cursor.execute('DROP TABLE "%s"' % table_name)
            new_sql = sql.replace('PRIMARY KEY',
                    'PRIMARY KEY AUTOINCREMENT')
            cursor.execute(new_sql)
            cursor.execute(('INSERT INTO "%s" '
                    '(' + ','.join(columns) + ') '
                    'SELECT ' + ','.join(columns)
                    + ' FROM "_temp_%s"') % (table_name, table_name))
            cursor.execute('DROP TABLE "_temp_%s"' % table_name)
        return True

    @staticmethod
    def table_rename(old_name, new_name):
        cursor = Transaction().connection.cursor()
        if (TableHandler.table_exist(old_name)
                and not TableHandler.table_exist(new_name)):
            cursor.execute('ALTER TABLE "%s" RENAME TO "%s"'
                % (old_name, new_name))
        # Rename history table
        old_history = old_name + "__history"
        new_history = new_name + "__history"
        if (TableHandler.table_exist(old_history)
                and not TableHandler.table_exist(new_history)):
            cursor.execute('ALTER TABLE "%s" RENAME TO "%s"'
                % (old_history, new_history))

    def column_exist(self, column_name):
        return column_name in self._columns

    def _recreate_table(self, new_columns):
        transaction = Transaction()
        database = transaction.database
        cursor = transaction.connection.cursor()
        temp_table = '__temp_%s' % self.table_name
        TableHandler.table_rename(self.table_name, temp_table)
        new_table = TableHandler(self._model, history=self.history)
        columns, old_columns = [], []
        for column, values in self._columns.items():
            typname = new_columns.get(column, {}).get(
                'typname', values['typname'])
            size = new_columns.get(column, {}).get('size', values['size'])
            new_column = new_columns.get(column, {}).get('name', column)
            new_table._add_raw_column(
                new_column, database.sql_type(typname), field_size=size)
            columns.append(new_column)
            old_columns.append(column)
        cursor.execute(('INSERT INTO "%s" ('
                + ','.join('"%s"' % x for x in columns)
                + ') SELECT '
                + ','.join('"%s"' % x for x in old_columns) + ' '
                + 'FROM "%s"') % (self.table_name, temp_table))
        cursor.execute('DROP TABLE "%s"' % temp_table)
        self._update_definitions()

    def column_rename(self, old_name, new_name):
        if self.column_exist(old_name):
            if not self.column_exist(new_name):
                self._recreate_table({old_name: {'name': new_name}})
            else:
                logger.warning(
                    'Unable to rename column %s on table %s to %s.',
                    old_name, self.table_name, new_name)

    def _update_definitions(self, columns=None, indexes=None):
        if columns is None and indexes is None:
            columns = indexes = True
        cursor = Transaction().connection.cursor()
        # Fetch columns definitions from the table
        if columns:
            cursor.execute('PRAGMA table_info("' + self.table_name + '")')
            self._columns = {}
            for _, column, type_, notnull, hasdef, _ in cursor.fetchall():
                column = re.sub(r'^\"|\"$', '', column)
                match = re.match(r'(\w+)(\((.*?)\))?', type_)
                if match:
                    typname = match.group(1).upper()
                    size = match.group(3) and int(match.group(3)) or 0
                else:
                    typname = type_.upper()
                    size = -1
                self._columns[column] = {
                    'notnull': notnull,
                    'hasdef': hasdef,
                    'size': size,
                    'typname': typname,
                }

        # Fetch indexes defined for the table
        if indexes:
            try:
                cursor.execute('PRAGMA index_list("' + self.table_name + '")')
            except IndexError:  # There is sometimes IndexError
                cursor.execute('PRAGMA index_list("' + self.table_name + '")')
            self._indexes = [l[1] for l in cursor.fetchall()]

    @property
    def _field2module(self):
        cursor = Transaction().connection.cursor()
        cursor.execute('SELECT f.name, f.module '
            'FROM ir_model_field f '
            'JOIN ir_model m on (f.model=m.id) '
            'WHERE m.model = ?',
            (self.object_name,))
        return dict(cursor)

    def alter_size(self, column_name, column_type):
        self._recreate_table({column_name: {'size': column_type}})

    def alter_type(self, column_name, column_type):
        self._recreate_table({column_name: {'typname': column_type}})

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
        cursor.execute(('ALTER TABLE "%s" ADD COLUMN "%s" %s') %
                       (self.table_name, column_name, column_type))

        if default:
            # check if table is non-empty:
            cursor.execute('SELECT 1 FROM "%s" limit 1' % self.table_name)
            if cursor.fetchone():
                # Populate column with default values:
                cursor.execute('UPDATE "' + self.table_name + '" '
                    'SET "' + column_name + '" = ?', (default(),))

        self._update_definitions(columns=True)

    def add_fk(self, column_name, reference, on_delete=None):
        warnings.warn('Unable to add foreign key with SQLite backend')

    def drop_fk(self, column_name, table=None):
        warnings.warn('Unable to drop foreign key with SQLite backend')

    def index_action(self, columns, action='add', where='', table=None):
        if isinstance(columns, str):
            columns = [columns]

        def stringify(column):
            if isinstance(column, str):
                return column
            else:
                return ('_'.join(
                        map(str, (column,) + column.params))
                    .replace('"', '')
                    .replace('?', '__'))

        name = [table or self.table_name]
        name.append('_'.join(map(stringify, columns)))
        if where:
            name.append('+where')
            name.append(stringify(where))
        name.append('index')
        index_name = self.convert_name('_'.join(name))

        cursor = Transaction().connection.cursor()
        if action == 'add':
            if index_name in self._indexes:
                return
            columns_quoted = []
            for column in columns:
                if isinstance(column, str):
                    columns_quoted.append('"%s"' % column)
                else:
                    columns_quoted.append(str(column))
            params = sum(
                (c.params for c in columns if hasattr(c, 'params')), ())
            if where:
                params += where.params
                where = ' WHERE %s' % where
            if params:
                warnings.warn('Unable to create index with parameters')
                return
            cursor.execute('CREATE INDEX "' + index_name + '" '
                'ON "' + self.table_name + '" '
                + '(' + ','.join(columns_quoted) + ')' + where,
                params)
            self._update_definitions(indexes=True)
        elif action == 'remove':
            if len(columns) == 1 and isinstance(columns[0], str):
                if self._field2module.get(columns[0],
                        self.module_name) != self.module_name:
                    return

            if index_name in self._indexes:
                cursor.execute('DROP INDEX "%s" ' % (index_name,))
                self._update_definitions(indexes=True)
        else:
            raise Exception('Index action not supported!')

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

    def drop_column(self, column_name):
        if not self.column_exist(column_name):
            return
        transaction = Transaction()
        database = transaction.database
        cursor = transaction.connection.cursor()
        temp_table = '__temp_%s' % self.table_name
        TableHandler.table_rename(self.table_name, temp_table)
        new_table = TableHandler(self._model, history=self.history)
        for name, values in self._columns.items():
            if name != column_name:
                typname = values['typname']
                size = values['size']
                new_table._add_raw_column(
                    name, database.sql_type(typname), field_size=size)
        columns_name = list(new_table._columns.keys())
        cursor.execute(('INSERT INTO "%s" ('
                        + ','.join('"%s"' % c for c in columns_name)
                        + ') SELECT '
                        + ','.join('"%s"' % c for c in columns_name) + ' '
                        + 'FROM "%s"') % (self.table_name, temp_table))
        cursor.execute('DROP TABLE "%s"' % temp_table)
        self._update_definitions()

    @staticmethod
    def drop_table(model, table, cascade=False):
        cursor = Transaction().connection.cursor()
        cursor.execute('DELETE from ir_model_data where '
            'model = \'%s\'' % model)

        query = 'DROP TABLE "%s"' % table
        if cascade:
            query = query + ' CASCADE'
        cursor.execute(query)
