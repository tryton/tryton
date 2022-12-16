# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import os

os.environ.setdefault('TRYTOND_DATABASE_URI', 'sqlite:///')
os.environ.setdefault('DB_NAME', ':memory:')

here = os.path.dirname(__file__)
readme = os.path.normpath(os.path.join(here, '..', '..', 'README.rst'))
