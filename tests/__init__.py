# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

try:
    from trytond.modules.company.tests.test_company import (
        suite, create_company, set_company)
except ImportError:
    from .test_company import suite, create_company, set_company

__all__ = ['suite', 'create_company', 'set_company']
