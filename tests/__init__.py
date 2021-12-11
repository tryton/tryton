# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

try:
    from trytond.modules.company.tests.test_company import (
        CompanyTestMixin, PartyCompanyCheckEraseMixin, create_company,
        create_employee, set_company, suite)
except ImportError:
    from .test_company import (
        CompanyTestMixin, PartyCompanyCheckEraseMixin, create_company,
        create_employee, set_company, suite)

__all__ = [
    'suite', 'create_company', 'set_company', 'create_employee',
    'PartyCompanyCheckEraseMixin', 'CompanyTestMixin']
