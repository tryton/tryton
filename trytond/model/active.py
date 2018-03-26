# This file is part of Tryton.  The COPYRIGHT file at the toplevel of this
# repository contains the full copyright notices and license terms.
from trytond.model import fields


class DeactivableMixin(object):
    "Mixin to allow to soft deletion of records"

    active = fields.Boolean("Active",
        help="Uncheck to exclude from future use.")

    @classmethod
    def default_active(cls):
        return True
