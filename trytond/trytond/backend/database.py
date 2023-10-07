# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from collections import namedtuple

from sql import For

DatabaseIntegrityError = None
DatabaseOperationalError = None
DatabaseTimeoutError = None

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
        raise NotImplementedError

    def get_connection(
            self, autocommit=False, readonly=False, statement_timeout=None):
        raise NotImplementedError

    def put_connection(self, connection, close=False):
        raise NotImplementedError

    def close(self):
        raise NotImplementedError

    @classmethod
    def create(cls, connection, database_name):
        raise NotImplementedError

    @classmethod
    def drop(cls, connection, database_name):
        raise NotImplementedError

    def list(self, hostname=None):
        raise NotImplementedError

    def init(self):
        raise NotImplementedError

    def test(self, hostname=None):
        '''
        Test if it is a Tryton database.
        '''
        raise NotImplementedError

    def nextid(self, connection, table, count=1):
        pass

    def setnextid(self, connection, table, value):
        pass

    def currid(self, connection, table):
        pass

    @classmethod
    def lock(cls, connection, table):
        raise NotImplementedError

    def lock_id(self, id, timeout=None):
        raise NotImplementedError

    def has_constraint(self, constraint):
        raise NotImplementedError

    def has_returning(self):
        return False

    def has_multirow_insert(self):
        return False

    def has_select_for(self):
        return False

    def get_select_for_skip_locked(self):
        return For

    def has_window_functions(self):
        return False

    def has_unaccent(self):
        return False

    def has_unaccent_indexable(self):
        return False

    def unaccent(self, value):
        return value

    def has_similarity(self):
        return False

    def similarity(self, column, value):
        raise NotImplementedError

    def has_search_full_text(self):
        return False

    def format_full_text(self, *documents, language=None):
        return '\n'.join(documents)

    def format_full_text_query(self, query, language=None):
        raise NotImplementedError

    def search_full_text(self, document, query):
        raise NotImplementedError

    def rank_full_text(self, document, query, normalize=None):
        "Return the expression that ranks query on document"
        raise NotImplementedError

    @classmethod
    def has_sequence(cls):
        return False

    def sequence_exist(self, connection, name):
        if not self.has_sequence():
            return
        raise NotImplementedError

    def sequence_create(
            self, connection, name, number_increment=1, start_value=1):
        if not self.has_sequence():
            return
        raise NotImplementedError

    def sequence_update(
            self, connection, name, number_increment=1, start_value=1):
        if not self.has_sequence():
            return
        raise NotImplementedError

    def sequence_rename(self, connection, old_name, new_name):
        if not self.has_sequence():
            return
        raise NotImplementedError

    def sequence_delete(self, connection, name):
        if not self.has_sequence():
            return
        raise NotImplementedError

    def sequence_next_number(self, connection, name):
        if not self.has_sequence():
            return
        raise NotImplementedError

    def has_channel(self):
        return False

    def sql_type(self, type_):
        pass

    def sql_format(self, type_, value):
        pass

    def json_get(self, column, key=None):
        raise NotImplementedError

    def json_key_exists(self, column, key):
        raise NotImplementedError

    def json_any_keys_exist(self, column, keys):
        raise NotImplementedError

    def json_all_keys_exist(self, column, keys):
        raise NotImplementedError

    def json_contains(self, column, json):
        raise NotImplementedError
