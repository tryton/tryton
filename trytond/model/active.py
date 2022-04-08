# This file is part of Tryton.  The COPYRIGHT file at the toplevel of this
# repository contains the full copyright notices and license terms.
from trytond.i18n import lazy_gettext
from trytond.pyson import Eval

from . import fields
from .model import Model
from .modelview import ModelView


class DeactivableMixin(Model):
    "Mixin to allow to soft deletion of records"
    __slots__ = ()

    active = fields.Boolean(
        lazy_gettext('ir.msg_active'),
        help=lazy_gettext('ir.msg_active_help'))

    @classmethod
    def default_active(cls):
        return True

    @classmethod
    def __post_setup__(cls):
        super().__post_setup__()

        inactive = ~Eval('active', cls.default_active())
        for name, field in cls._fields.items():
            if name == 'active':
                continue
            if 'readonly' in field.states:
                field.states['readonly'] |= inactive
            else:
                field.states['readonly'] = inactive

        if issubclass(cls, ModelView):
            for states in cls._buttons.values():
                if 'readonly' in states:
                    states['readonly'] |= inactive
                else:
                    states['readonly'] = inactive
                if 'active' not in states.setdefault('depends', []):
                    states['depends'].append('active')
