# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.


from trytond.pool import PoolMeta

from .marketing import MarketingCampaignUTM


class ShortenedURL(metaclass=PoolMeta):
    __name__ = 'web.shortened_url'

    def access(self, **values):
        url = super().access(**values)
        if isinstance(self.record, MarketingCampaignUTM):
            url = self.record.add_utm_parameters(url)
        return url
