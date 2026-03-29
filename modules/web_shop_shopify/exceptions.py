# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.exceptions import TrytonException, UserError, UserWarning


class GraphQLException(TrytonException):
    def __init__(self, message):
        super().__init__(message)
        self.message = message


class ShopifyError(UserError):
    pass


class ShopifyCredentialWarning(UserWarning):
    pass
