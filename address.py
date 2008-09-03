#This file is part of Tryton.  The COPYRIGHT file at the top level of this repository contains the full copyright notices and license terms.
from trytond.osv import fields, OSV
import urllib

class Address(OSV):
    _name = 'relationship.address'

    google_maps_url = fields.Function('get_google_maps_url', type="char",
            string="Google Maps")

    def get_google_maps_url(self, cursor, user, ids, name, arg, context=None):
        if context is None:
            context = {}
        res = {}
        lang = context.get('language', 'en_US')[:2]
        for address in self.browse(cursor, user, ids, context=context):
            query = ''
            if address.street:
                query += ' ' + address.street
            if address.streetbis:
                query += ' ' + address.streetbis
            if address.zip:
                query += ' ' + address.zip
            if address.city:
                query += ' ' + address.city
            if address.country:
                query += ' ' + address.country.name
            if address.state:
                query += ' ' + address.state.name
            if query.strip():
                res[address.id] = 'http://maps.google.com/maps?hl=%s&q=%s' % \
                        (lang, urllib.quote(query.strip().encode('utf-8')))
            else:
                res[address.id] = ''
        return res

Address()
