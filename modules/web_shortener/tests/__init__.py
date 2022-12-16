# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

try:
    from trytond.modules.web_shortener.tests.test_web_shortener import suite
except ImportError:
    from .test_web_shortener import suite

__all__ = ['suite']
