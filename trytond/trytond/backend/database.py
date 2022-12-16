# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from collections import namedtuple
from sql import For

DatabaseIntegrityError = None
DatabaseOperationalError = None

SQLType = namedtuple('SQLType', 'base type')


class DatabaseInterface(object):
    '''
    Define generic interface for database connection
    '''
    flavor = None
    IN_MAX = 1000

    def __new__(cls, name=''):
        return object.__new__(cls)

    def __init__(self, name=''):
        self.name = name

    def connect(self):
        '''
        Connect to the database

        :return: the database
        '''
        raise NotImplementedError

    def get_connection(self, autocommit, readonly=False):
        '''Retrieve a connection on the database

        :param autocommit: a boolean to activate autocommit
        :param readonly: a boolean to specify if the transaction is readonly
        '''
        raise NotImplementedError

    def put_connection(self, connection, close=False):
        '''Release the connection

        :param close: if close is True the connection is discarded
        '''
        raise NotImplementedError

    def close(self):
        '''
        Close all connection
        '''
        raise NotImplementedError

    @classmethod
    def create(cls, connection, database_name):
        '''
        Create a database

        :param connection: the connection to the database
        :param database_name: the new database name
        '''
        raise NotImplementedError

    def drop(self, connection, database_name):
        '''
        Drop a database

        :param connection: the connection to the database
        :param database_name: the database name
        '''
        raise NotImplementedError

    def list(self, hostname=None):
        '''
        Get the list of database

        :return: a list of database name
        '''
        raise NotImplementedError

    def init(self):
        '''
        Initialize a database
        '''
        raise NotImplementedError

    def test(self, hostname=None):
        '''
        Test if it is a Tryton database.
        '''
        raise NotImplementedError

    def nextid(self, connection, table):
        '''
        Return the next sequenced id for a table.

        :param connection: a connection on the database
        :param table: the table name
        :return: an integer
        '''

    def setnextid(self, connection, table, value):
        '''
        Set the current sequenced id for a table.

        :param connection: a connection on the database
        :param table: the table name
        '''

    def currid(self, connection, table):
        '''
        Return the current sequenced id for a table.

        :param connection: a connection on the database
        :param table: the table name
        :return: an integer
        '''

    def update_auto_increment(self, connection, table, value):
        '''
        Update auto_increment value of table

        :param connection: a connection on the database
        :param table: the table name
        :param value: the auto_increment value
        '''
        pass

    @classmethod
    def lock(cls, connection, table):
        '''
        Lock the table

        :param connection: a connection on the database
        :param table: the table name
        '''
        raise NotImplementedError

    def lock_id(self, id, timeout=None):
        """Return SQL function to lock resource"""
        raise NotImplementedError

    def has_constraint(self, constraint):
        '''
        Return True if database handle constraint.

        :return: a boolean
        '''
        raise NotImplementedError

    def has_returning(self):
        '''
        Return True if database implements RETURNING clause in INSERT or UPDATE
        statements.

        :return: a boolean
        '''
        return False

    def has_multirow_insert(self):
        'Return True if database supports multirow insert'
        return False

    def has_select_for(self):
        "Return if database supports FOR UPDATE/SHARE clause in SELECT."
        return False

    def get_select_for_skip_locked(self):
        "Return For class with skip locked"
        return For

    def has_window_functions(self):
        "Return if database supports window functions."
        return False

    def has_unaccent(self):
        "Return if database supports unaccentuated searches"
        return False

    def unaccent(self, value):
        "Return the expression to use for unaccentuated columns"
        return value

    @classmethod
    def has_sequence(cls):
        "Return if database supports sequence querying and assignation"
        return False

    def sequence_exist(self, connection, name):
        "Return if a sequence exists"
        if not self.has_sequence():
            return
        raise NotImplementedError

    def sequence_create(
            self, connection, name, number_increment=1, start_value=1):
        "Creates a sequence"
        if not self.has_sequence():
            return
        raise NotImplementedError

    def sequence_update(
            self, connection, name, number_increment=1, start_value=1):
        "Modifies a sequence"
        if not self.has_sequence():
            return
        raise NotImplementedError

    def sequence_rename(self, connection, old_name, new_name):
        "Renames a sequence"
        if not self.has_sequence():
            return
        raise NotImplementedError

    def sequence_delete(self, connection, name):
        "Removes a sequence"
        if not self.has_sequence():
            return
        raise NotImplementedError

    def sequence_next_number(self, connection, name):
        "Gets the next number of a sequence"
        if not self.has_sequence():
            return
        raise NotImplementedError

    def has_channel(self):
        "Return True if database supports LISTEN/NOTIFY channel"
        return False

    def sql_type(self, type_):
        'Return the SQLType tuple corresponding to the SQL type'
        pass

    def sql_format(self, type_, value):
        'Return value correctly casted into type_'
        pass

    def json_get(self, column, key=None):
        "Return the JSON value of the JSON key"
        raise NotImplementedError

    def json_key_exists(self, column, key):
        "Return expression for key exists in JSON column"
        raise NotImplementedError

    def json_any_keys_exist(self, column, keys):
        "Return expression for any keys exist in JSON column"
        raise NotImplementedError

    def json_all_keys_exist(self, column, keys):
        "Rteurn expression for all keys exist in JSON column"
        raise NotImplementedError

    def json_contains(self, column, json):
        "Return expression for column contains JSON"
        raise NotImplementedError
