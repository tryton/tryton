# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.exceptions import UserError, UserWarning
from trytond.model.exceptions import ValidationError


class AssignError(UserError):
    pass


class LocationValidationError(ValidationError):
    pass


class PeriodCloseError(UserError):
    pass


class InventoryValidationError(ValidationError):
    pass


class InventoryCountWarning(UserWarning):
    pass


class MoveOriginWarning(UserWarning):
    pass


class ProductCostPriceError(ValidationError):
    pass
