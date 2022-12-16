# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

try:
    from trytond.modules.user_role.tests.test_user_role import suite
except ImportError:
    from .test_user_role import suite

__all__ = ['suite']
