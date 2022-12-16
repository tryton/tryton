# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.exceptions import UserError, UserWarning
from trytond.model.exceptions import ValidationError


class PaymentTermValidationError(ValidationError):
    pass


class PaymentTermComputeError(UserError):
    pass


class InvoiceTaxValidationError(ValidationError):
    pass


class InvoiceNumberError(ValidationError):
    pass


class InvoiceValidationError(ValidationError):
    pass


class InvoiceLineValidationError(ValidationError):
    pass


class PayInvoiceError(UserError):
    pass


class InvoicePaymentTermDateWarning(UserWarning):
    pass


class InvoiceFutureWarning(UserWarning):
    pass


class InvoiceSimilarWarning(UserWarning):
    pass
