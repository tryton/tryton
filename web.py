# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import PoolMeta


class ShortenedURL(metaclass=PoolMeta):
    __name__ = 'web.shortened_url'

    @classmethod
    def _get_models(cls):
        return super()._get_models() + [
            'marketing.automation.record.activity',
            ]

    @classmethod
    def _get_methods(cls):
        return super()._get_methods() + [
            'marketing.automation.record.activity|on_email_opened',
            'marketing.automation.record.activity|on_email_clicked',
            ]
