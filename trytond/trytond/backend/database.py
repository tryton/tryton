#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

DatabaseIntegrityError = None
DatabaseOperationalError = None

class DatabaseInterface(object):
    '''
    Define generic interface for database connection
    '''

    def __new__(cls, database_name=''):
        return object.__new__(cls)

    def __init__(self, database_name=''):
        self.database_name = database_name

    def connect(self):
        '''
        Connect to the database

        :return: the database
        '''
        raise

    def cursor(self, autocommit=False):
        '''
        Retreive a cursor on the database

        :param autocommit: a boolean to active autocommit
        :return: a Cursor
        '''
        raise

    def close(self):
        '''
        Close all connection
        '''
        raise

    def create(self, cursor, database_name):
        '''
        Create a database

        :param database_name: the database name
        '''
        raise

    def drop(self, cursor, database_name):
        '''
        Drop a database

        :param cursor: a cursor on an other database
        :param database_name: the database name
        '''
        raise

    @staticmethod
    def dump(database_name):
        '''
        Dump a database

        :param database_name: the database name
        :return: the dump
        '''
        raise

    @staticmethod
    def restore(database_name, data):
        '''
        Restore a database

        :param database_name: the database name
        :param data: the data
        :return: True if succeed
        '''

    @staticmethod
    def list(cursor):
        '''
        Get the list of database

        :return: a list of database name
        '''
        raise

    @staticmethod
    def init(cursor):
        '''
        Initialize a database

        :param cursor: a cursor on the database
        '''
        raise


class CursorInterface(object):
    '''
    Define generic interface for database cursor
    '''
    sql_log = False
    IN_MAX = 1000

    def __init__(self):
        raise

    def execute(self, sql, params=None):
        '''
        Execute a query

        :param sql: a sql query string
        :param params: a tuple or list of parameters
        '''
        raise

    def close(self):
        '''
        Close the cursor
        '''
        raise

    def commit(self):
        '''
        Commit the cursor
        '''
        raise

    def rollback(self):
        '''
        Rollback the cursor
        '''
        raise

    def test(self):
        '''
        Test if it is a Tryton database.
        '''
        raise
