# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.exceptions import UserError, UserWarning


class ShopifyError(UserError):
    pass


class ShopifyCredentialWarning(UserWarning):
    pass
