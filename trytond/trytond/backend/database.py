# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
DatabaseIntegrityError = None
DatabaseOperationalError = None


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

    def list(self):
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

    def test(self):
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

    def has_constraint(self):
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
