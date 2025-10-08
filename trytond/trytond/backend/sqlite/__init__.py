# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import sqlite3
import sys

from .database import (
    Database, DatabaseDataError, DatabaseIntegrityError,
    DatabaseOperationalError, DatabaseTimeoutError)
from .table import TableHandler

if sqlite3.sqlite_version_info < (3, 30, 0):
    sys.exit("Tryton sqlite backend requires version 3.30.0 or higher")

__all__ = [
    Database, TableHandler,
    DatabaseIntegrityError, DatabaseDataError, DatabaseOperationalError,
    DatabaseTimeoutError]
