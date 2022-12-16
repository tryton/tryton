# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

try:
    from trytond.modules.party_siret.tests.test_party_siret import suite
except ImportError:
    from .test_party_siret import suite

__all__ = ['suite']
