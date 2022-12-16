# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

try:
    from trytond.modules.party_avatar.tests.test_party_avatar import suite  # noqa: E501
except ImportError:
    from .test_party_avatar import suite

__all__ = ['suite']
