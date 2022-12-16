# This file is part of Tryton.  The COPYRIGHT file at the toplevel of this
# repository contains the full copyright notices and license terms.
from trytond.i18n import lazy_gettext
from trytond.model import fields


class DeactivableMixin(object):
    "Mixin to allow to soft deletion of records"
    __slots__ = ()

    active = fields.Boolean(
        lazy_gettext('ir.msg_active'),
        help=lazy_gettext('ir.msg_active_help'))

    @classmethod
    def default_active(cls):
        return True
