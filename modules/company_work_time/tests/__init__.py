# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

try:
    from trytond.modules.company_work_time.tests.test_company_work_time import suite  # noqa: E501
except ImportError:
    from .test_company_work_time import suite

__all__ = ['suite']
