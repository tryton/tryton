# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import base64
import datetime as dt
import json
from decimal import Decimal


class JSONDecoder(object):

    decoders = {}

    @classmethod
    def register(cls, klass, decoder):
        assert klass not in cls.decoders
        cls.decoders[klass] = decoder

    def __call__(self, dct):
        if dct.get('__class__') in self.decoders:
            return self.decoders[dct['__class__']](dct)
        return dct


JSONDecoder.register('datetime',
    lambda dct: dt.datetime(dct['year'], dct['month'], dct['day'],
        dct['hour'], dct['minute'], dct['second'], dct['microsecond']))
JSONDecoder.register('date',
    lambda dct: dt.date(dct['year'], dct['month'], dct['day']))
JSONDecoder.register('time',
    lambda dct: dt.time(dct['hour'], dct['minute'], dct['second'],
        dct['microsecond']))
JSONDecoder.register('timedelta',
    lambda dct: dt.timedelta(seconds=dct['seconds']))


def _bytes_decoder(dct):
    cast = bytearray if bytes == str else bytes
    return cast(base64.decodebytes(dct['base64'].encode('utf-8')))


JSONDecoder.register('bytes', _bytes_decoder)
JSONDecoder.register('Decimal', lambda dct: Decimal(dct['decimal']))


class JSONEncoder(json.JSONEncoder):

    serializers = {}

    @classmethod
    def register(cls, klass, encoder):
        assert klass not in cls.serializers
        cls.serializers[klass] = encoder

    def default(self, obj):
        marshaller = self.serializers.get(type(obj),
            super(JSONEncoder, self).default)
        return marshaller(obj)


JSONEncoder.register(dt.datetime,
    lambda o: {
        '__class__': 'datetime',
        'year': o.year,
        'month': o.month,
        'day': o.day,
        'hour': o.hour,
        'minute': o.minute,
        'second': o.second,
        'microsecond': o.microsecond,
        })
JSONEncoder.register(dt.date,
    lambda o: {
        '__class__': 'date',
        'year': o.year,
        'month': o.month,
        'day': o.day,
        })
JSONEncoder.register(dt.time,
    lambda o: {
        '__class__': 'time',
        'hour': o.hour,
        'minute': o.minute,
        'second': o.second,
        'microsecond': o.microsecond,
        })
JSONEncoder.register(dt.timedelta,
    lambda o: {
        '__class__': 'timedelta',
        'seconds': o.total_seconds(),
        })


def _bytes_encoder(o):
    return {
        '__class__': 'bytes',
        'base64': base64.encodebytes(o).decode('utf-8'),
        }


JSONEncoder.register(bytes, _bytes_encoder)
JSONEncoder.register(bytearray, _bytes_encoder)
JSONEncoder.register(Decimal,
    lambda o: {
        '__class__': 'Decimal',
        'decimal': str(o),
        })
