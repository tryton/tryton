# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import csv
import os
import logging.config
from io import StringIO

__all__ = ['app']

# Logging must be set before importing
logging_config = os.environ.get('TRYTOND_LOGGING_CONFIG')
if logging_config:
    logging.config.fileConfig(logging_config)

from trytond.pool import Pool
from trytond.wsgi import app

Pool.start()
# TRYTOND_CONFIG it's managed by importing config
db_names = os.environ.get('TRYTOND_DATABASE_NAMES')
if db_names:
    # Read with csv so database name can include special chars
    reader = csv.reader(StringIO(db_names))
    for db_name in next(reader):
        Pool(db_name).init()
