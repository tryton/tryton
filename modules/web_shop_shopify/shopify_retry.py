# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import time

from pyactiveresource.connection import ClientError
from shopify import Limits
from shopify.base import ShopifyConnection

from trytond.protocols.wrappers import HTTPStatus


def patch():
    def _open(*args, **kwargs):
        while True:
            try:
                return func(*args, **kwargs)
            except ClientError as e:
                if e.response.code == HTTPStatus.TOO_MANY_REQUESTS:
                    retry_after = float(
                        e.response.headers.get('Retry-After', 2))
                    time.sleep(retry_after)
                else:
                    raise
            else:
                try:
                    if Limits.credit_maxed():
                        time.sleep(0.5)
                except Exception:
                    pass

    if ShopifyConnection._open == _open:
        return
    func = ShopifyConnection._open
    ShopifyConnection._open = _open
