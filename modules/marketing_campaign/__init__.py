# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

__all__ = ['Parameter', 'MarketingCampaignMixin', 'MarketingCampaignUTM']


def __getattr__(name):
    if name in {'Parameter', 'MarketingCampaignMixin', 'MarketingCampaignUTM'}:
        from . import marketing
        return getattr(marketing, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
