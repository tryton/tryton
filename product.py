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
        if name != 'forecast_quantity' and context.get('stock_date'):
            if context['stock_date'] != datetime.date.today():
                context = context.copy()
                context['stock_date'] = datetime.date.today()
        pbl = self.products_by_location(cursor, user,
                location_ids=context['locations'], product_ids=ids,
                with_childs=True, context=context)

        res = {}.fromkeys(ids, 0.0)
        for (location, product) in zip(context['locations'], ids):
            res[product] += pbl.get((location, product), 0.0)
        return res

    def _search_quantity_eval_domain(self, line, domain):
        res = True
        for field, operator, operand in domain:
            value = line.get(field)
            if value == None:
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
        if (name != 'forecast_quantity') and context.get('stock_date'):
            if context['stock_date'] != datetime.date.today():
                context = context.copy()
                del context['stock_date']

        pbl = self.products_by_location(
            cursor, user, location_ids=context['locations'], with_childs=True,
            skip_zero=False, context=context).iteritems()

        processed_lines = []
        for (location, product), quantity in pbl:
            processed_lines.append({'location': location, #XXX useful ?
                                    'product': product,
                                    name: quantity})

        res= [line['product'] for line in processed_lines \
                    if self._search_quantity_eval_domain(line, domain)]
        return [('id', 'in', res)]


    def raw_products_by_location(self, cursor, user, location_ids,
            product_ids=None, with_childs=False, context=None):
        """
        Return a list like : [(location, product, uom, qty)] for each
        location and product given as argument.
        Null qty are not returned and the tuple (location, product,uom)
        is unique.
        If with_childs, childs location are also computed.
        The key stock_date in context can be used to compute stock for
        other date than today.
        """
        location_obj = self.pool.get('stock.location')
        if not location_ids:
            return []

        rule_obj = self.pool.get('ir.rule')
        move_query, move_val = rule_obj.domain_get(cursor, user, 'stock.move')

        if context.get('stock_date') and \
                context['stock_date'] > datetime.date.today():
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
            where_vals = args
        else:
            where_clause = " IN (" + \
                ",".join(["%s" for i in location_ids]) + ") "
            where_vals = location_ids[:]

        where_clause += " AND " + move_query + " "
        where_vals += move_val

        if product_ids:
            where_clause += "AND product in (" + \
                ",".join(["%s" for i in product_ids]) + ")"
            where_vals += product_ids

        where_clause += ' AND ('\
            '(effective_date IS NULL '\
            'AND ( planned_date <= %s or planned_date IS NULL)) '\
            'OR effective_date <= %s'\
            ')'
        if context.get('stock_date'):
            where_date = [context['stock_date'], context['stock_date']]
        else:
            where_date = [datetime.date.today(), datetime.date.today()]

        cursor.execute(select_clause % (
            ",".join(["%s" for i in in_states]), where_clause,
            ",".join(["%s" for i in out_states]), where_clause),
            in_states + where_vals + where_date + \
                    out_states + where_vals + where_date)
        res = cursor.fetchall()
        return res

    def products_by_location(self, cursor, user, location_ids,
            product_ids=None, with_childs=False, skip_zero=True, context=None):
        """
        Return a list like :
            [{location: 1, product: 1, uom: 1, qty: 2}]
            for each location and product given as argument.
        The key stock_date in context can be used to compute stock for other
        date than today.
        If with_childs, childs locations are also computed.
        If skip_zero, list item with quantity equal to zero are not returned.
        If no product_ids are given the computation is done on all products.
        """
        uom_obj = self.pool.get("product.uom")
        product_obj = self.pool.get("product.product")
        location_obj = self.pool.get("stock.location")

        if not location_ids:
            return []

        res = {}
        raw_lines = self.raw_products_by_location(cursor, user, location_ids,
                product_ids, with_childs=with_childs, context=context)

        res_location_ids = []
        uom_ids = []
        res_product_ids = []
        for line in raw_lines:
            for id_list, position in ((res_location_ids, 0), (uom_ids, 1),
                                      (res_product_ids, 1)):
                if line[position] not in id_list:
                    id_list.append(line[position])

        if not product_ids:
            product_ids = self.pool.get("product.product").search(
                cursor, user, [], context=context)
        uom_by_id = dict([(x.id, x) for x in uom_obj.browse(
                cursor, user, uom_ids, context=context)])
        default_uom = dict((x.id, x.default_uom) for x in product_obj.browse(
                cursor, user, product_ids, context=context))

        for line in raw_lines:
            location, product, uom, quantity = line
            key = (location, product)
            res.setdefault(key, 0.0)
            res[key] += uom_obj.compute_qty(cursor, user, uom_by_id[uom],
                    quantity, default_uom[product], context=context)

        # Propagate quantities on from child locations to their parents
        if with_childs:
            # Fetch all child locations
            all_location_ids = location_obj.search(
                cursor, user, [('parent', 'child_of', location_ids)],
                context=context)
            locations = location_obj.browse(cursor, user, all_location_ids,
                                            context=context)
            # Generate a set of locations without childs and a dict
            # giving the parent of each location.
            leafs = set(all_location_ids)
            parent = {}
            for location in locations:
                if not location.parent: continue
                if location.parent.id in leafs:
                    leafs.remove(location.parent.id)
                parent[location.id] = location.parent.id

            while leafs:
                next_leafs = set()
                for l in leafs:
                    if l not in parent:
                        continue
                    next_leafs.add(parent[l])
                    for product in res_product_ids:
                        res.setdefault((parent[l], product), 0)
                        res[(parent[l], product)] += res.get((l,product), 0)
                leafs = next_leafs

        # Complete result with missing products if asked
        if not skip_zero:
            keys = ((l,p) for l in location_ids for p in product_ids)
            for location_id, product_id in keys:
                if (location_id, product_id) not in res:
                    res[(location_id, product_id)] = 0.0

        return res



    def view_header_get(self, cursor, user, value, view_type='form',
            context=None):
        if not context.get('locations'):
            return False
        location_obj = self.pool.get('stock.location')
        locations = location_obj.browse(cursor, user, context.get('locations'),
                                        context=context)
        return value + " (" + ",".join([l.name for l in locations]) + ")"

Product()


class ChooseStockDateInit(WizardOSV):
    _name = 'stock.product_stock_date.init'
    forecast_date = fields.Date(
        'Forecast Date', help='Allow to compute expected '\
            'stock quantities for this date.\n'\
            '* An empty value is an infinite date in the future.\n'\
            '* A date in the past will provide historical values.')
ChooseStockDateInit()

class OpenLocation(Wizard):
    'Products by Locations'
    _name = 'stock.location.open'
    states = {
        'init': {
            'result': {
                'type': 'form',
                'object': 'stock.product_stock_date.init',
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

        if context == None: context = {}
        context['product'] = data['id']
        if data['form']['forecast_date']:
            context['stock_date'] = data['form']['forecast_date']
        else:
            context['stock_date'] = datetime.date.max
        res['context'] = str(context)

        return res

OpenLocation()
