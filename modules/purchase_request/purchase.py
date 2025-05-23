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
        result = func(cls, purchases)
        with without_check_access():
            requests = [
                r for p in cls.browse(purchases)
                for l in p.lines
                for r in l.requests]
            Request.update_state(requests)
        return result
    return wrapper


class Purchase(metaclass=PoolMeta):
    __name__ = 'purchase.purchase'

    @classmethod
    def check_modification(cls, mode, purchases, values=None, external=False):
        super().check_modification(
            mode, purchases, values=values, external=external)
        if mode == 'delete':
            for purchase in purchases:
                for line in purchase.lines:
                    if line.requests:
                        raise AccessError(gettext(
                                'purchase_request.msg_purchase_delete_request',
                                purchase=purchase.rec_name))

    @classmethod
    @ModelView.button
    @Workflow.transition('confirmed')
    def confirm(cls, purchases):
        for purchase in purchases:
            purchase.check_request_warehouse()
        super().confirm(purchases)

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
        super().cancel(purchases)

    @classmethod
    @ModelView.button
    @process_request
    def process(cls, purchases):
        super().process(purchases)


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
    def on_delete(cls, lines):
        pool = Pool()
        Request = pool.get('purchase.request')
        callback = super().on_delete(lines)
        requests = {r for l in lines for r in l.requests}
        if requests:
            requests = Request.browse(requests)
            callback.append(lambda: Request.update_state(requests))
        return callback
