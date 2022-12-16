# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

try:
    from trytond.modules.notification_email.tests.test_notification_email \
        import suite
except ImportError:
    from .test_notification_email import suite

__all__ = ['suite']
