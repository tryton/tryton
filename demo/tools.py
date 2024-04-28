# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import hashlib

from proteus import Model


def format_warning(name, records):
    key = '|'.join(map(str, records)).encode('utf-8')
    return '%s.%s' % (hashlib.md5(key).hexdigest(), name)


def skip_warning(config, name, records):
    Warning_ = Model.get('res.user.warning')
    Warning_(user=config.user, name=format_warning(name, records)).save()
