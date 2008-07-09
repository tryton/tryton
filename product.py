#This file is part of Tryton.  The COPYRIGHT file at the top level of this repository contains the full copyright notices and license terms.
from trytond.osv import fields, OSV
from trytond.wizard import Wizard, WizardOSV
import datetime

class Product(OSV):
    "Product"
    _name = "product.product"
    _inherit = "product.product"

    quantity = fields.Function('get_quantity', type='float', string='Quantity',
                               fnct_search='search_quantity', readonly=True)
    forecast_quantity = fields.Function(
        'get_quantity', type='float', string='Forecast Quantity',
        fnct_search='search_quantity', readonly=True)

    def get_quantity(self, cursor, user, ids, name, args, context=None):
        if not (context and context.get('locations')):
            return dict([(id, 0.0) for id in ids])

        pbl = self.products_by_location(cursor, user,
                location_ids=context['locations'], product_ids=ids,
                forecast=(name == 'forecast_quantity'), with_childs=True,
                context=context)
        res = {}
        for product_id in ids:
            res[product_id] = 0.0
        for line in pbl:
            res[line['product']] += line['quantity']
        return res

    def _search_quantity_eval_domain(self, line, domain):
        res = True
        for field, operator, operand in domain:
            value = line.get(field)
            if not value:
                return False
            if operator not in ("=", ">=", "<=", ">", "<", "!="):
                return False
            if operator == "=":
                operator= "=="
            res = res and (eval(str(value) + operator + str(operand)))
        return res

    def search_quantity(self, cursor, user, name, domain=[], context=None):
        if not (context and context.get('locations')):
            return []

        pbl = self.products_by_location(cursor, user,
                location_ids=context['locations'],
                forecast=(name == 'forecast_quantity'), with_childs=True,
                context=context)

        if name == 'forecast_quantity':
            for line in pbl:
                line['forecast_quantity'] = line['quantity']
                del line['quantity']

        res= [line['product'] for line in pbl \
                    if self._search_quantity_eval_domain(line, domain)]
        return [('id', 'in', res)]


    def raw_products_by_location(self, cursor, user, location_ids,
            product_ids=None, forecast=False, with_childs=False, context=None):
        """
        Return a list like : [(location, product, uom, qty)] for each
        location and product given as argument. Null qty are not
        returned and the tuple (location, product,uom) is unique.
        """
        location_obj = self.pool.get('stock.location')
        if not location_ids:
            return []

        if forecast and not (context.get('forecast_date') and \
                context['forecast_date'] < datetime.date.today()):
            in_states = ['done', 'assigned', 'draft']
            out_states = ['done', 'assigned', 'draft']
        else:
            in_states = context and context.get('in_states') or ['done']
            out_states = context and context.get('out_states') or ['done']

        select_clause = \
                "SELECT location, product, uom, sum(quantity) AS quantity "\
                "FROM ( "\
                    "SELECT to_location AS location, product, uom, "\
                        "sum(quantity) AS quantity "\
                    "FROM stock_move "\
                    "WHERE state IN (%s) " \
                        "AND to_location %s "\
                    "GROUP BY to_location, product ,uom "\
                    "UNION  "\
                    "SELECT from_location AS location, product, uom, "\
                        "-sum(quantity) AS quantity "\
                    "FROM stock_move "\
                    "WHERE state IN (%s) " \
                        "AND from_location %s "\
                    "GROUP BY from_location, product, uom "\
                ") AS T GROUP BY T.location, T.product, T.uom"

        if with_childs:
            query, args = location_obj.search(cursor, user, [
                ('parent', 'child_of', location_ids),
                ], context=context, query_string=True)
            where_clause = " IN (" + query + ") "
            where_ids = args
        else:
            where_clause = " IN (" + \
                ",".join(["%s" for i in location_ids]) + ") "
            where_ids = location_ids[:]
        if product_ids:
            where_clause += "AND product in (" + \
                ",".join(["%s" for i in product_ids]) + ")"
            where_ids += product_ids

        if forecast and context.get('forecast_date'):
            where_clause += ' AND ('\
                '(effective_date IS NULL '\
                'AND ( planned_date <= %s or planned_date IS NULL)) '\
                'OR effective_date <= %s'\
                ')'
            where_date = [context['forecast_date'],context['forecast_date']]
        else:
            where_date = []

        cursor.execute(select_clause % (
            ",".join(["%s" for i in in_states]), where_clause,
            ",".join(["%s" for i in out_states]), where_clause),
            in_states + where_ids + where_date + \
                    out_states + where_ids + where_date)

        return cursor.fetchall()

    def products_by_location(self, cursor, user, location_ids,
            product_ids=None, forecast=False, with_childs=False, context=None):

        uom_obj = self.pool.get("product.uom")
        product_obj = self.pool.get("product.product")

        if not location_ids:
            return []

        res = {}
        raw_lines = self.raw_products_by_location(cursor, user, location_ids,
                product_ids, forecast=forecast, with_childs=with_childs,
                context=context)

        uom_ids = []
        product_ids = []
        for line in raw_lines:
            uom_ids.append(line[2])
            product_ids.append(line[1])

        uom_by_id = dict([(x.id, x) for x in uom_obj.browse(
                cursor, user, uom_ids, context=context)])
        default_uom = dict((x.id, x.default_uom) for x in product_obj.browse(
                cursor, user, product_ids, context=context))

        for line in raw_lines:
            location, product, uom, quantity = line
            key = (location, product, default_uom[product].id)
            res.setdefault(key, 0.0)
            res[key] += uom_obj.compute_qty(cursor, user, uom_by_id[uom],
                    quantity, default_uom[product], context=context)
        return [{
            'location': key[0],
            'product':key[1],
            'uom': key[2],
            'quantity': val,
            } for key, val in res.iteritems()]

    def view_header_get(self, cursor, user, value, view_type='form',
            context=None):
        if not context.get('locations'):
            return False
        location_obj = self.pool.get('stock.location')
        locations = location_obj.browse(cursor, user, context.get('locations'),
                                        context=context)
        return value + " (" + ",".join([l.name for l in locations]) + ")"

Product()


class ChooseForecatsDateInit(WizardOSV):
    _name = 'stock.product_forecast_date.init'
    forecast_date = fields.Date(
        'Forecast Date', help='Allow to compute expected '\
            'stock quantities for this date.\n'\
            '* An empty value is an infinite date in the future.\n'\
            '* A date in the past will provide historical values.')
ChooseForecatsDateInit()

class OpenLocation(Wizard):
    'Products by Locations'
    _name = 'stock.location.open'
    states = {
        'init': {
            'result': {
                'type': 'form',
                'object': 'stock.product_forecast_date.init',
                'state': [
                    ('end', 'Cancel', 'tryton-cancel'),
                    ('open', 'Open', 'tryton-ok', True),
                ],
            },
        },
        'open': {
            'result': {
                'type': 'action',
                'action': '_action_open_location',
                'state': 'end',
            },
        },
    }

    def _action_open_location(self, cursor, user, data, context=None):
        model_data_obj = self.pool.get('ir.model.data')
        act_window_obj = self.pool.get('ir.action.act_window')

        model_data_ids = model_data_obj.search(cursor, user, [
            ('fs_id', '=', 'act_location_quantity_tree'),
            ('module', '=', 'stock'),
            ], limit=1, context=context)
        model_data = model_data_obj.browse(cursor, user, model_data_ids[0],
                context=context)
        res = act_window_obj.read(cursor, user, model_data.db_id, context=context)

        context = {'product': data['id']}
        if data['form']['forecast_date']:
            context['forecast_date'] = data['form']['forecast_date']
        res['context'] = str(context)

        return res

OpenLocation()
