#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import urllib
from trytond.model import fields
from trytond.transaction import Transaction
from trytond.pool import PoolMeta

__all__ = ['Address']
__metaclass__ = PoolMeta


class Address:
    __name__ = 'party.address'

    google_maps_url = fields.Function(fields.Char('Google Maps',
            on_change_with=['street', 'streetbis', 'zip', 'city', 'country',
                'subdivision']), 'on_change_with_google_maps_url')

    def on_change_with_google_maps_url(self, name=None):
        lang = Transaction().language[:2]
        url = ''
        for value in (
                self.street,
                self.streetbis,
                self.zip,
                self.city,
                self.country.name if self.country else None,
                self.subdivision.name if self.subdivision else None,
                ):
            if value:
                if isinstance(value, str):
                    url += ' ' + value.decode('utf-8')
                else:
                    url += ' ' + value
        if url.strip():
            return 'http://maps.google.com/maps?hl=%s&q=%s' % \
                (lang, urllib.quote(url.strip().encode('utf-8')))
        return ''
