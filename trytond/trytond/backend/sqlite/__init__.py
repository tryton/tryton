# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import sqlite3
import sys

from .database import (
    Database, DatabaseDataError, DatabaseIntegrityError,
    DatabaseOperationalError, DatabaseTimeoutError)
from .table import TableHandler

MAX_QUERY_PARAMS = 200  # estimation from the SQLITE_MAX_EXPR_DEPTH=1_000

if sqlite3.sqlite_version_info < (3, 30, 0):
    sys.exit("Tryton sqlite backend requires version 3.30.0 or higher")

__all__ = [
    Database,
    DatabaseDataError,
    DatabaseIntegrityError,
    DatabaseOperationalError,
    DatabaseTimeoutError,
    MAX_QUERY_PARAMS,
    TableHandler,
    ]
