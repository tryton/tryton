# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

try:
    from trytond.modules.google_maps.tests.test_google_maps import suite
except ImportError:
    from .test_google_maps import suite

__all__ = ['suite']
