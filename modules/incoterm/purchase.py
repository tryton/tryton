# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.i18n import gettext
from trytond.model import fields
from trytond.pool import PoolMeta
from trytond.pyson import Eval

from .common import IncotermMixin, IncotermAvailableMixin


class Purchase(IncotermAvailableMixin, metaclass=PoolMeta):
    __name__ = 'purchase.purchase'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.incoterm_location.search_context['incoterm_type'] = 'purchase'

    @property
    @fields.depends('party')
    def _party_incoterms(self):
        return self.party.purchase_incoterms if self.party else []

    @property
    @fields.depends(methods=['_party_incoterms'])
    def _incoterm_required(self):
        return bool(self._party_incoterms)

    def check_for_quotation(self):
        from trytond.modules.purchase.exceptions import PurchaseQuotationError
        super().check_for_quotation()
        if not self.incoterm and self._incoterm_required:
            for line in self.lines:
                if line.product and line.product.type in {'goods', 'assets'}:
                    raise PurchaseQuotationError(
                        gettext('incoterm'
                            '.msg_purchase_incoterm_required_for_quotation',
                            purchase=self.rec_name))


class RequestQuotation(IncotermMixin, metaclass=PoolMeta):
    __name__ = 'purchase.request.quotation'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.incoterm_location.search_context['incoterm_type'] = 'purchase'

    @classmethod
    def _incoterm_editable_states(cls):
        return ~Eval('state').in_(
            ['draft', 'sent', 'rejected', 'received', 'cancelled']), ['state']

    @classmethod
    def _incoterm_related_party(cls):
        return Eval('supplier'), ['supplier']


class RequestCreatePurchase(metaclass=PoolMeta):
    __name__ = 'purchase.request.create_purchase'

    @classmethod
    def _group_purchase_key(cls, requests, request):
        return super()._group_purchase_key(requests, request) + (
            ('incoterm',
                request.best_quotation_line.quotation.incoterm
                if request.best_quotation_line else None),
            ('incoterm_location',
                request.best_quotation_line.quotation.incoterm_location
                if request.best_quotation_line else None),
            )
