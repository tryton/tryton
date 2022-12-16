# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

try:
    from trytond.modules.edocument_unece.tests.test_edocument_unece import suite  # noqa: E501
except ImportError:
    from .test_edocument_unece import suite

__all__ = ['suite']
