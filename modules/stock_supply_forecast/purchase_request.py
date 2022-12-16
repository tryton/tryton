#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import Model
from trytond.pool import Pool


class PurchaseRequest(Model):
    _name = 'purchase.request'

    def generate_requests(self):
        forecast_obj = Pool().get('stock.forecast')
        date_obj = Pool().get('ir.date')

        today = date_obj.today()

        forecast_ids = forecast_obj.search([
                ('to_date', '>=', today),
                ('state', '=', 'done'),
                ])
        forecast_obj.create_moves(forecast_ids)
        super(PurchaseRequest, self).generate_requests()
        forecast_obj.delete_moves(forecast_ids)

PurchaseRequest()
