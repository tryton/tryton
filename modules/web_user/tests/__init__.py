# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

try:
    from trytond.modules.web_user.tests.test_web_user import suite
except ImportError:
    from .test_web_user import suite

__all__ = ['suite']
