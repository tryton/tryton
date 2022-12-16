# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.exceptions import UserError, UserWarning
from trytond.model.exceptions import ValidationError


class PurchaseUOMWarning(UserWarning):
    pass


class PurchaseQuotationError(ValidationError):
    pass


class PartyLocationError(UserError):
    pass
