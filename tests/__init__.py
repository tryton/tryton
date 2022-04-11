# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

try:
    from trytond.modules.account_es_sii.tests.test_account_es_sii import \
        suite  # noqa: E501
except ImportError:
    from .test_account_es_sii import suite

__all__ = ['suite']
