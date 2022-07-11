# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.i18n import lazy_gettext
from trytond.model import Model, fields
from trytond.pool import Pool
from trytond.pyson import Eval, If

__all__ = ['IncotermMixin', 'IncotermAvailableMixin']


class IncotermMixin(Model):

    incoterm = fields.Many2One(
        'incoterm.incoterm', lazy_gettext('incoterm.msg_incoterm'),
        ondelete='RESTRICT')
    incoterm_location = fields.Many2One(
        'party.address', lazy_gettext('incoterm.msg_incoterm_location'),
        ondelete='RESTRICT',
        search_order=[
            ('is_incoterm_related', 'DESC NULLS LAST'),
            ('party.distance', 'ASC NULLS LAST'),
            ('id', None),
            ])

    @classmethod
    def __setup__(cls):
        super().__setup__()
        readonly = cls._incoterm_readonly_state()
        cls.incoterm.states = {
            'readonly': readonly,
            }

        cls.incoterm_location.states = {
            'readonly': readonly,
            'invisible': ~Eval('incoterm', False),
            }
        related_party, related_party_depends = cls._incoterm_related_party()
        cls.incoterm_location.search_context = {
            'related_party': related_party,
            }
        cls.incoterm_location.depends = {'incoterm'} | related_party_depends

    @classmethod
    def _incoterm_readonly_state(cls):
        return ~Eval('state').in_(['draft'])

    @classmethod
    def _incoterm_related_party(cls):
        return Eval('party'), {'party'}

    @property
    def incoterm_name(self):
        name = ''
        if self.incoterm:
            name = self.incoterm.rec_name
            if self.incoterm_location:
                name += ' %s' % self.incoterm_location.rec_name
        return name


class IncotermAvailableMixin(IncotermMixin):

    available_incoterms = fields.Function(fields.Many2Many(
            'incoterm.incoterm', None, None, "Available Incoterms"),
        'on_change_with_available_incoterms')
    incoterm_location_required = fields.Function(fields.Boolean(
            lazy_gettext('incoterm.msg_incoterm_location_required')),
        'on_change_with_incoterm_location_required')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        readonly = cls._incoterm_readonly_state()
        cls.incoterm.domain = [
            If(~readonly,
                ('id', 'in', Eval('available_incoterms', [])),
                ()),
            ]
        cls.incoterm_location.states['required'] = (
            Eval('incoterm_location_required', False))

    @fields.depends('company', 'party', methods=['_get_incoterm_pattern'])
    def on_change_with_available_incoterms(self, name=None):
        pool = Pool()
        Incoterm = pool.get('incoterm.incoterm')
        pattern = self._get_incoterm_pattern()
        incoterms = Incoterm.get_incoterms(self.company, pattern)
        if self.party:
            party_incoterms = {r.incoterm for r in self._party_incoterms}
        else:
            party_incoterms = set()
        return [
            i.id for i in incoterms
            if not party_incoterms or i in party_incoterms]

    @fields.depends()
    def _get_incoterm_pattern(self):
        return {}

    @fields.depends('incoterm')
    def on_change_with_incoterm_location_required(self, name=None):
        if self.incoterm:
            return self.incoterm.location

    @fields.depends(methods=['_set_default_incoterm'])
    def on_change_company(self):
        try:
            super_on_change = super().on_change_company
        except AttributeError:
            pass
        else:
            super_on_change()
        self._set_default_incoterm()

    @fields.depends(methods=['_set_default_incoterm'])
    def on_change_party(self):
        try:
            super_on_change = super().on_change_party
        except AttributeError:
            pass
        else:
            super_on_change()
        self._set_default_incoterm()

    @fields.depends('incoterm', 'party', 'company',
        methods=['_party_incoterms'])
    def on_change_incoterm(self):
        if self.incoterm:
            if self._party_incoterms:
                for record in self._party_incoterms:
                    if record.company and record.company != self.company:
                        continue
                    if record.incoterm == self.incoterm:
                        self.incoterm_location = record.incoterm_location
                        break
                else:
                    self.incoterm_location = None
        else:
            self.incoterm_location = None

    @fields.depends('incoterm', 'party', 'company',
        methods=['on_change_with_available_incoterms',
            '_incoterm_required', '_party_incoterms'])
    def _set_default_incoterm(self):
        self.available_incoterms = self.on_change_with_available_incoterms()
        if not self.available_incoterms:
            self.incoterm = None
            self.incoterm_location = None
        elif self._incoterm_required:
            if self.incoterm not in self.available_incoterms:
                if len(self.available_incoterms) == 1:
                    self.incoterm, = self.available_incoterms
                else:
                    self.incoterm = None
                self.incoterm_location = None
            if self.party and self._party_incoterms:
                for record in self._party_incoterms:
                    if record.company and record.company != self.company:
                        continue
                    if record.incoterm in self.available_incoterms:
                        self.incoterm = record.incoterm
                        self.incoterm_location = record.incoterm_location
                        break
                else:
                    self.incoterm = None
                    self.incoterm_location = None
        elif self.incoterm not in self.available_incoterms:
            self.incoterm = None
            self.incoterm_location = None

    @property
    def _party_incoterms(self):
        raise NotImplementedError

    @property
    def _incoterm_required(self):
        raise NotImplementedError
