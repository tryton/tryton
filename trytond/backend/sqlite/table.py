# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.transaction import Transaction
from trytond.backend.table import TableHandlerInterface
import logging
import re
import warnings

__all__ = ['TableHandler']

logger = logging.getLogger(__name__)


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
                    'SELECT ' + ','.join(columns) +
                    ' FROM "%s"') % (table_name, table_name))
            cursor.execute('DROP TABLE "%s"' % table_name)
            new_sql = sql.replace('PRIMARY KEY',
                    'PRIMARY KEY AUTOINCREMENT')
            cursor.execute(new_sql)
            cursor.execute(('INSERT INTO "%s" '
                    '(' + ','.join(columns) + ') '
                    'SELECT ' + ','.join(columns) +
                    ' FROM "_temp_%s"') % (table_name, table_name))
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

    @staticmethod
    def sequence_exist(sequence_name):
        return True

    @staticmethod
    def sequence_rename(old_name, new_name):
        pass

    def column_exist(self, column_name):
        return column_name in self._columns

    def column_rename(self, old_name, new_name, exception=False):
        cursor = Transaction().connection.cursor()
        if self.column_exist(old_name) and \
                not self.column_exist(new_name):
            temp_table = '_temp_%s' % self.table_name
            TableHandler.table_rename(self.table_name, temp_table)
            new_table = TableHandler(self._model, history=self.history)
            for column, (notnull, hasdef, size, typname) \
                    in self._columns.iteritems():
                if column == old_name:
                    column = new_name
                new_table.add_raw_column(column, typname, False,
                    field_size=size)
            new_columns = new_table._columns.keys()
            old_columns = [x if x != old_name else new_name
                for x in new_columns]
            cursor.execute(('INSERT INTO "%s" (' +
                    ','.join('"%s"' % x for x in new_columns) +
                    ') SELECT ' +
                    ','.join('"%s"' % x for x in old_columns) + ' ' +
                    'FROM "%s"') % (self.table_name, temp_table))
            cursor.execute('DROP TABLE "%s"' % temp_table)
            self._update_definitions()
        elif exception and self.column_exist(new_name):
            raise Exception('Unable to rename column %s.%s to %s.%s: '
                '%s.%s already exist!'
                % (self.table_name, old_name, self.table_name, new_name,
                    self.table_name, new_name))

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
        warnings.warn('Unable to alter size of column with SQLite backend')

    def alter_type(self, column_name, column_type):
        warnings.warn('Unable to alter type of column with SQLite backend')

    def db_default(self, column_name, value):
        warnings.warn('Unable to set default on column with SQLite backend')

    def add_raw_column(self, column_name, column_type, column_format,
            default_fun=None, field_size=None, migrate=True, string=''):
        if self.column_exist(column_name):
            if not migrate:
                return
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
                if field_size is None:
                    if self._columns[column_name]['size'] > 0:
                        self.alter_size(column_name, base_type)
                elif self._columns[column_name]['size'] == field_size:
                    pass
                elif (self._columns[column_name]['size'] > 0
                        and self._columns[column_name]['size'] < field_size):
                    self.alter_size(column_name, column_type[1])
                else:
                    logger.warning(
                        'Unable to migrate column %s on table %s '
                        'from varchar(%s) to varchar(%s).',
                        column_name, self.table_name,
                        self._columns[column_name]['size'] > 0
                        and self._columns[column_name]['size'] or "",
                        field_size)
            return

        cursor = Transaction().connection.cursor()
        column_type = column_type[1]
        default = ''
        cursor.execute(('ALTER TABLE "%s" ADD COLUMN "%s" %s' + default) %
                       (self.table_name, column_name, column_type))

        if column_format:
            # check if table is non-empty:
            cursor.execute('SELECT 1 FROM "%s" limit 1' % self.table_name)
            if cursor.fetchone():
                # Populate column with default values:
                default = None
                if default_fun is not None:
                    default = default_fun()
                cursor.execute('UPDATE "' + self.table_name + '" '
                    'SET "' + column_name + '" = ?',
                    (column_format(default),))

        self._update_definitions(columns=True)

    def add_fk(self, column_name, reference, on_delete=None):
        warnings.warn('Unable to add foreign key with SQLite backend')

    def drop_fk(self, column_name, table=None):
        warnings.warn('Unable to drop foreign key with SQLite backend')

    def index_action(self, column_name, action='add', table=None):
        if isinstance(column_name, basestring):
            column_name = [column_name]
        index_name = self.table_name + "_" + '_'.join(column_name) + "_index"

        cursor = Transaction().connection.cursor()
        if action == 'add':
            if index_name in self._indexes:
                return
            cursor.execute('CREATE INDEX "' + index_name + '" '
                'ON "' + self.table_name + '" ( ' +
                ','.join('"' + x + '"' for x in column_name) +
                ')')
            self._update_definitions(indexes=True)
        elif action == 'remove':
            if len(column_name) == 1:
                if self._field2module.get(column_name[0],
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

    def add_constraint(self, ident, constraint, exception=False):
        warnings.warn('Unable to add constraint with SQLite backend')

    def drop_constraint(self, ident, exception=False, table=None):
        warnings.warn('Unable to drop constraint with SQLite backend')

    def drop_column(self, column_name, exception=False):
        warnings.warn('Unable to drop column with SQLite backend')

    @staticmethod
    def drop_table(model, table, cascade=False):
        cursor = Transaction().connection.cursor()
        cursor.execute('DELETE from ir_model_data where '
            'model = \'%s\'' % model)

        query = 'DROP TABLE "%s"' % table
        if cascade:
            query = query + ' CASCADE'
        cursor.execute(query)
