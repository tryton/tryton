# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

try:
    from trytond.modules.authentication_sms.tests.test_authentication_sms import suite, send_sms  # noqa: E501
except ImportError:
    from .test_authentication_sms import suite, send_sms

__all__ = ['suite', 'send_sms']
