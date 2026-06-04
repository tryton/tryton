# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from .database import (
    Database, DatabaseDataError, DatabaseIntegrityError,
    DatabaseOperationalError, DatabaseTimeoutError, dict_row, namedtuple_row,
    scalar_row)
from .table import TableHandler

MAX_QUERY_PARAMS = 50_000  # rounded down from 65_535

__all__ = [
    Database,
    DatabaseDataError,
    DatabaseIntegrityError,
    DatabaseOperationalError,
    DatabaseTimeoutError,
    dict_row,
    namedtuple_row,
    scalar_row,
    MAX_QUERY_PARAMS,
    TableHandler,
    ]
