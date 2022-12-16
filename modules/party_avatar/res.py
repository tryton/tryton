# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import PoolMeta


class User(metaclass=PoolMeta):
    __name__ = 'res.user'

    def get_avatar_badge_url(self, name):
        url = super().get_avatar_badge_url(name)
        if self.company:
            url = self.company.avatar_url
        return url
