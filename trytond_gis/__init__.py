# This file is part of trytond_gis.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.config import config

from .const import WGS_84

__version__ = "5.8.0"


class _GeoJSON(dict):

    def __init__(self, *args, **kwargs):
        super(_GeoJSON, self).__init__(*args, **kwargs)
        if 'meta' not in self:
            self['meta'] = {}
        if 'srid' not in self['meta']:
            self['meta']['srid'] = config.getint(
                'database', 'srid', default=WGS_84)
