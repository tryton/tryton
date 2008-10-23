#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.osv import fields, OSV
import urllib

class Address(OSV):
    _name = 'party.address'

    google_maps_url = fields.Function('get_google_maps_url', type="char",
            string="Google Maps", on_change_with=['street', 'streetbis',
                'zip', 'city', 'country', 'subdivision'])

    def _get_url(self, cursor, user, vals, context=None):
        if context is None:
            context = {}
        lang = context.get('language', 'en_US')[:2]
        url = ''
        for i in ['street', 'streetbis', 'zip', 'city',
                'country', 'subdivision']:
            if vals.get(i):
                url += ' ' + vals[i]
        if url.strip():
            url = 'http://maps.google.com/maps?hl=%s&q=%s' % \
                    (lang, urllib.quote(url.strip().encode('utf-8')))
        else:
            url = ''
        return url

    def on_change_with_google_maps_url(self, cursor, user, ids, vals,
            context=None):
        country_obj = self.pool.get('country.country')
        subdivision_obj = self.pool.get('country.subdivision')

        vals = vals.copy()

        if vals.get('country'):
            country = country_obj.browse(cursor, user, vals['country'],
                    context=context)
            vals['country'] = country.name

        if vals.get('subdivision'):
            subdivision = subdivision_obj.browse(cursor, user,
                    vals['subdivision'], context=context)
            vals['subdivision'] = subdivision.name

        return self._get_url(cursor, user, vals, context=context)

    def get_google_maps_url(self, cursor, user, ids, name, arg, context=None):
        res = {}
        for address in self.browse(cursor, user, ids, context=context):
            vals = {
                'street': address.street,
                'streetbis': address.streetbis,
                'zip': address.zip,
                'city': address.city,
                'country': address.country and address.country.name or False,
                'subdivision': address.subdivision and \
                        address.subdivision.name or False,
            }
            res[address.id] = self._get_url(cursor, user, vals,
                    context=context)
        return res

Address()
