# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from functools import wraps

from trytond.i18n import gettext
from trytond.model import ModelView, Workflow, fields
from trytond.model.exceptions import AccessError
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval
from trytond.transaction import without_check_access

from .exceptions import PurchaseWarehouseWarning


def process_request(func):
    # Must be run after the purchase transition
    # such as purchase has the proper state
    @wraps(func)
    def wrapper(cls, purchases):
        pool = Pool()
        Request = pool.get('purchase.request')
        func(cls, purchases)
        requests = [r for p in purchases for l in p.lines for r in l.requests]
        Request.update_state(requests)
    return wrapper


class Purchase(metaclass=PoolMeta):
    __name__ = 'purchase.purchase'

    @classmethod
    def delete(cls, purchases):
        cls.check_delete_purchase_request(purchases)
        super(Purchase, cls).delete(purchases)

    @classmethod
    @without_check_access
    def check_delete_purchase_request(cls, purchases):
        for purchase in purchases:
            for line in purchase.lines:
                if line.requests:
                    raise AccessError(
                        gettext('purchase_request.msg_purchase_delete_request',
                            purchase=purchase.rec_name))

    @classmethod
    @ModelView.button
    @Workflow.transition('confirmed')
    def confirm(cls, purchases):
        for purchase in purchases:
            purchase.check_request_warehouse()
        super(Purchase, cls).confirm(purchases)

    def check_request_warehouse(self):
        pool = Pool()
        Warning = pool.get('res.user.warning')
        for line in self.lines:
            for request in line.requests:
                if request.warehouse != self.warehouse:
                    w_name = 'check_request_warehouse_%s_%s_%s' % (
                        self.id, self.warehouse.id, request.warehouse.id)
                    if Warning.check(w_name):
                        raise PurchaseWarehouseWarning(
                            w_name,
                            gettext('purchase_request'
                                '.msg_purchase_request_warehouse',
                                purchase=self.rec_name,
                                purchase_warehouse=self.warehouse.rec_name,
                                request=request.rec_name,
                                request_warehouse=request.warehouse.rec_name))

    @classmethod
    @ModelView.button
    @process_request
    @Workflow.transition('cancelled')
    def cancel(cls, purchases):
        super(Purchase, cls).cancel(purchases)

    @classmethod
    @process_request
    @Workflow.transition('done')
    def do(cls, purchases):
        super(Purchase, cls).do(purchases)


class Line(metaclass=PoolMeta):
    __name__ = 'purchase.line'

    requests = fields.One2Many(
        'purchase.request', 'purchase_line', "Requests", readonly=True,
        states={
            'invisible': ~Eval('requests'),
            })

    @classmethod
    def copy(cls, lines, default=None):
        default = default.copy() if default is not None else {}
        default.setdefault('requests')
        return super().copy(lines, default=default)

    @classmethod
    def delete(cls, lines):
        pool = Pool()
        Request = pool.get('purchase.request')
        with without_check_access():
            requests = [r for l in cls.browse(lines) for r in l.requests]
        super().delete(lines)
        with without_check_access():
            Request.update_state(requests)
