# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import string
import logging
from urllib.parse import urljoin, quote

from sql.aggregate import Count

from trytond.config import config
from trytond.model import fields, ModelSQL, ModelView
from trytond.pool import Pool
from trytond.tools import grouped_slice, reduce_ids
from trytond.transaction import Transaction
from trytond.url import http_host
from trytond.wsgi import Base64Converter

ALPHABET = string.digits + string.ascii_lowercase
URL_BASE = config.get('web', 'shortener_base', default=http_host())
logger = logging.getLogger(__name__)


class ShortenedURL(ModelSQL, ModelView):
    "Short URL"
    __name__ = 'web.shortened_url'

    shortened_url = fields.Function(
        fields.Char("Shortened URL"), 'get_url')
    redirect_url = fields.Char("Redirect URL", readonly=True, required=True)
    record = fields.Reference("Record", selection='get_models', readonly=True)
    method = fields.Selection('get_methods', "Method", readonly=True)
    count = fields.Function(fields.Integer("Click Count"), 'get_count')

    @classmethod
    def get_url(cls, shortened_urls, name):
        urls = {}

        url_parts = {
            'database': Base64Converter(None).to_url(
                Transaction().database.name).decode('utf-8'),
            }
        for shortened in shortened_urls:
            url_parts['short_id'] = cls._shorten(shortened.id)
            urls[shortened.id] = urljoin(
                URL_BASE, quote('/s/%(database)s$%(short_id)s' % url_parts))
        return urls

    @classmethod
    def get_count(cls, shortened_urls, name):
        pool = Pool()
        URLAccess = pool.get('web.shortened_url.access')

        access = URLAccess.__table__()
        cursor = Transaction().connection.cursor()

        counts = {s.id: 0 for s in shortened_urls}
        for sub_ids in grouped_slice(shortened_urls):
            cursor.execute(*access.select(
                    access.url, Count(access.id),
                    where=reduce_ids(access.url, sub_ids),
                    group_by=[access.url]))
            counts.update(cursor.fetchall())
        return counts

    @classmethod
    def _get_models(cls):
        return []

    @classmethod
    def get_models(cls):
        pool = Pool()
        Model = pool.get('ir.model')
        models = cls._get_models()
        models = Model.search([
                ('model', 'in', models),
                ])
        return [(None, '')] + [(m.model, m.name) for m in models]

    @classmethod
    def _get_methods(cls):
        return []

    @fields.depends('record')
    def get_methods(self):
        def func(option):
            if not self.record:
                return True
            else:
                name = option[0].split('|')[0]
                return self.record.__class__.__name__ == name
        return [(None, '')] + list(filter(func,
                ((m, m) for m in self._get_methods())))

    @classmethod
    def get(cls, shortened_id):
        id = cls._expand(shortened_id)
        return cls.search([('id', '=', id)], limit=1)[0]

    def access(self, **values):
        pool = Pool()
        URLAccess = pool.get('web.shortened_url.access')

        URLAccess(url=self, **values).save()
        if self.record and self.method:
            model, method = self.method.split('|')
            if model == self.record.__class__.__name__:
                method = getattr(self.record.__class__.__queue__, method)
                method([self.record])
        return self.redirect_url

    @staticmethod
    def _shorten(integer):
        "Turns an integer into a string in a given alphabet"
        key_part = []
        while integer:
            integer, remainder = divmod(integer, len(ALPHABET))
            key_part.append(ALPHABET[remainder])
        else:
            if not key_part:
                key_part.append('0')
        return ''.join(reversed(key_part))

    @staticmethod
    def _expand(key):
        "Turns a key from a given alphabet to the corresponding ID"
        return int(key, len(ALPHABET))


class URLAccess(ModelSQL):
    "URL Access"
    __name__ = 'web.shortened_url.access'

    url = fields.Many2One('web.shortened_url', "URL", required=True)
