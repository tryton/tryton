# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.config import config

DatabaseIntegrityError = None
DatabaseOperationalError = None


class DatabaseInterface(object):
    '''
    Define generic interface for database connection
    '''
    flavor = None

    def __new__(cls, database_name=''):
        return object.__new__(cls)

    def __init__(self, database_name=''):
        self.database_name = database_name

    def connect(self):
        '''
        Connect to the database

        :return: the database
        '''
        raise NotImplementedError

    def cursor(self, autocommit=False, readonly=False):
        '''
        Retreive a cursor on the database

        :param autocommit: a boolean to active autocommit
        :return: a Cursor
        '''
        raise NotImplementedError

    def close(self):
        '''
        Close all connection
        '''
        raise NotImplementedError

    @staticmethod
    def create(cursor, database_name):
        '''
        Create a database

        :param database_name: the database name
        '''
        raise NotImplementedError

    @staticmethod
    def drop(cursor, database_name):
        '''
        Drop a database

        :param cursor: a cursor on an other database
        :param database_name: the database name
        '''
        raise NotImplementedError

    @staticmethod
    def dump(database_name):
        '''
        Dump a database

        :param database_name: the database name
        :return: the dump
        '''
        raise NotImplementedError

    @staticmethod
    def restore(database_name, data):
        '''
        Restore a database

        :param database_name: the database name
        :param data: the data
        :return: True if succeed
        '''
        raise NotImplementedError

    @staticmethod
    def list(cursor):
        '''
        Get the list of database

        :return: a list of database name
        '''
        raise NotImplementedError

    @staticmethod
    def init(cursor):
        '''
        Initialize a database

        :param cursor: a cursor on the database
        '''
        raise NotImplementedError


class CursorInterface(object):
    '''
    Define generic interface for database cursor
    '''
    IN_MAX = 1000
    cache_keys = {'language', 'fuzzy_translation', '_datetime'}

    def __init__(self):
        self.cache = {}

    def get_cache(self):
        from trytond.cache import LRUDict
        from trytond.transaction import Transaction
        user = Transaction().user
        context = Transaction().context
        keys = tuple(((key, context[key]) for key in sorted(self.cache_keys)
                if key in context))
        return self.cache.setdefault((user, keys),
            LRUDict(config.getint('cache', 'model')))

    def execute(self, sql, params=None):
        '''
        Execute a query

        :param sql: a sql query string
        :param params: a tuple or list of parameters
        '''
        raise NotImplementedError

    def close(self, close=False):
        '''
        Close the cursor

        :param close: boolean to not release cursor in pool
        '''
        raise NotImplementedError

    def commit(self):
        '''
        Commit the cursor
        '''
        for cache in self.cache.itervalues():
            cache.clear()

    def rollback(self):
        '''
        Rollback the cursor
        '''
        for cache in self.cache.itervalues():
            cache.clear()

    def test(self):
        '''
        Test if it is a Tryton database.
        '''
        raise NotImplementedError

    def nextid(self, table):
        '''
        Return the next sequenced id for a table.

        :param table: the table name
        :return: an integer
        '''

    def setnextid(self, table, value):
        '''
        Set the current sequenced id for a table.

        :param table: the table name
        '''

    def currid(self, table):
        '''
        Return the current sequenced id for a table.

        :param table: the table name
        :return: an integer
        '''

    def lastid(self):
        '''
        Return the last id inserted.

        :return: an integer
        '''

    def lock(self, table):
        '''
        Lock the table

        :param table: the table name
        '''
        raise NotImplementedError

    def has_constraint(self):
        '''
        Return True if database handle constraint.

        :return: a boolean
        '''
        raise NotImplementedError

    def update_auto_increment(self, table, value):
        '''
        Update auto_increment value of table

        :param table: the table name
        :param value: the auto_increment value
        '''
        pass

    def has_returning(self):
        '''
        Return True if database implements RETURNING clause in INSERT or UPDATE
        statements.

        :return: a boolean
        '''

    def has_multirow_insert(self):
        'Return True if database supports multirow insert'
        return False

    def __build_dict(self, row):
        return dict((desc[0], row[i])
                for i, desc in enumerate(self.description))

    def dictfetchone(self):
        row = self.fetchone()
        if row:
            return self.__build_dict(row)
        else:
            return row

    def dictfetchmany(self, size):
        rows = self.fetchmany(size)
        return [self.__build_dict(row) for row in rows]

    def dictfetchall(self):
        rows = self.fetchall()
        return [self.__build_dict(row) for row in rows]
