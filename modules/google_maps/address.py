# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import urllib.parse

from trytond.model import fields
from trytond.transaction import Transaction
from trytond.pool import PoolMeta


class Address(metaclass=PoolMeta):
    __name__ = 'party.address'

    google_maps_url = fields.Function(fields.Char('Google Maps'),
        'on_change_with_google_maps_url')

    @fields.depends('name', 'street', 'zip', 'city', 'country', 'subdivision')
    def on_change_with_google_maps_url(self, name=None):
        lang = Transaction().language[:2]
        url = ' '.join(self.get_full_address('full_address').splitlines())
        if url.strip():
            return 'http://maps.google.com/maps?hl=%s&q=%s' % \
                (lang, urllib.parse.quote(url))
        return ''
