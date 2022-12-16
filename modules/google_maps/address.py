#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import urllib
from trytond.model import ModelView, ModelSQL, fields
from trytond.transaction import Transaction
from trytond.pool import Pool


class Address(ModelSQL, ModelView):
    _name = 'party.address'

    google_maps_url = fields.Function(fields.Char('Google Maps',
        on_change_with=['street', 'streetbis', 'zip', 'city', 'country',
            'subdivision']), 'get_google_maps_url')

    def _get_url(self, vals):
        lang = Transaction().language[:2]
        url = ''
        for i in ['street', 'streetbis', 'zip', 'city',
                'country', 'subdivision']:
            if vals.get(i):
                if isinstance(vals[i], str):
                    url += ' ' + vals[i].decode('utf-8')
                else:
                    url += ' ' + vals[i]
        if url.strip():
            url = 'http://maps.google.com/maps?hl=%s&q=%s' % \
                    (lang, urllib.quote(url.strip().encode('utf-8')))
        else:
            url = ''
        return url

    def on_change_with_google_maps_url(self, vals):
        country_obj = Pool().get('country.country')
        subdivision_obj = Pool().get('country.subdivision')

        vals = vals.copy()

        if vals.get('country'):
            country = country_obj.browse(vals['country'])
            vals['country'] = country.name

        if vals.get('subdivision'):
            subdivision = subdivision_obj.browse(vals['subdivision'])
            vals['subdivision'] = subdivision.name

        return self._get_url(vals)

    def get_google_maps_url(self, ids, name):
        res = {}
        for address in self.browse(ids):
            vals = {
                'street': address.street,
                'streetbis': address.streetbis,
                'zip': address.zip,
                'city': address.city,
                'country': address.country and address.country.name or None,
                'subdivision': address.subdivision and \
                        address.subdivision.name or None,
            }
            res[address.id] = self._get_url(vals)
        return res

Address()
