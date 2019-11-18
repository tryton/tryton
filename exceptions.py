# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.exceptions import UserError, UserWarning
from trytond.model.exceptions import ValidationError


class PeriodNotFoundError(UserError):
    pass


class PeriodValidationError(ValidationError):
    pass


class ClosePeriodError(PeriodValidationError):
    pass


class PeriodDatesError(PeriodValidationError):
    pass


class PeriodSequenceError(PeriodValidationError):
    pass


class FiscalYearNotFoundError(UserError):
    pass


class FiscalYearValidationError(ValidationError):
    pass


class FiscalYearDatesError(FiscalYearValidationError):
    pass


class FiscalYearSequenceError(FiscalYearValidationError):
    pass


class FiscalYearCloseError(UserError):
    pass


class FiscalYearReOpenError(UserError):
    pass


class AccountMissing(UserError):
    pass


class SecondCurrencyError(ValidationError):
    pass


class ChartWarning(UserWarning):
    pass


class PostError(UserError):
    pass


class MoveDatesError(ValidationError):
    pass


class CancelWarning(UserWarning):
    pass


class ReconciliationError(ValidationError):
    pass


class DeleteDelegatedWarning(UserWarning):
    pass


class CancelDelegatedWarning(UserWarning):
    pass


class GroupLineError(UserError):
    pass
