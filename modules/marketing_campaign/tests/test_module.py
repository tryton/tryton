# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from unittest.mock import patch

from trytond.model import ModelStorage
from trytond.modules.marketing_campaign import MarketingCampaignUTM
from trytond.pool import Pool
from trytond.tests.test_tryton import ModuleTestCase, with_transaction


class MarketingCampaignTestCase(ModuleTestCase):
    "Test Marketing Campaign module"
    module = 'marketing_campaign'
    extras = [
        'marketing_email', 'marketing_automation', 'sale', 'sale_opportunity',
        'sale_point', 'web_shortener']

    @with_transaction()
    def test_shortened_url_add_utm(self):
        "Test add UTM to shortened URL"
        pool = Pool()
        ShortenedURL = pool.get('web.shortened_url')
        URLAccess = pool.get('web.shortened_url.access')
        Campaign = pool.get('marketing.campaign')

        with patch.object(URLAccess, 'save'):
            class Record(MarketingCampaignUTM, ModelStorage):
                __slots__ = ('marketing_campaign',)
                id = 1

            Record.__setup__()
            Record.__post_setup__()

            campaign = Campaign(name='campaign')
            campaign.save()
            record = Record()
            record.marketing_campaign = campaign
            shortened_url = ShortenedURL(
                redirect_url='http://example.com/',
                record=record,
                method=None)

            self.assertEqual(
                shortened_url.access(),
                'http://example.com/?utm_campaign=campaign')


del ModuleTestCase
