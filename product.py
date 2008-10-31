#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.osv import fields, OSV
from trytond.wizard import Wizard, WizardOSV
import datetime


class Template(OSV):
    _name = "product.template"

    quantity = fields.Function('get_quantity', type='float', string='Quantity')
    forecast_quantity = fields.Function('get_quantity', type='float',
            string='Forecast Quantity')

    def get_quantity(self, cursor, user, ids, name, args, context=None):
        res = {}
        if name not in ('quantity', 'forecast_quantity'):
            raise Exception('Bad argument')

        for template in self.browse(cursor, user, ids, context=context):
            res[template.id] = 0.0
            for product in template.products:
                res[template.id] += product[name]
        return res

Template()

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
        date_obj = self.pool.get('ir.date')

        if not (context and context.get('locations')):
            return dict([(id, 0.0) for id in ids])

        if name == 'quantity' and \
                context.get('stock_date_end') != \
                date_obj.today(cursor, user, context=context):

            context = context.copy()
            context['stock_date_end'] = date_obj.today(
                cursor, user, context=context)

        if name == 'forecast_quantity' and not context.get('stock_date_end'):
            context = context.copy()
            context['stock_date_end'] = datetime.date.max
        pbl = self.products_by_location(cursor, user,
                location_ids=context['locations'], product_ids=ids,
                with_childs=True, context=context)

        res = {}.fromkeys(ids, 0.0)
        for location in context['locations']:
            for product in ids:
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

    def search_quantity(self, cursor, user, name, domain=None, context=None):
        date_obj = self.pool.get('ir.date')

        if not (context and context.get('locations') and domain):
            return []
        if (name != 'forecast_quantity') and context.get('stock_date_end'):
            if context['stock_date_end'] != date_obj.today(cursor, user,
                    context=context):
                context = context.copy()
                del context['stock_date_end']

        if name == 'forecast_quantity' and not context.get('stock_date_end'):
            context = context.copy()
            context['stock_date_end'] = datetime.date.max

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



    def products_by_location(self, cursor, user, location_ids,
            product_ids=None, with_childs=False, skip_zero=True, context=None):
        """
        Return a dict like : {(location, product): qty} for each
        location and product given as argument, the implicit uom is
        the default uom on the product.
        - The keys stock_date_end stock_date_start in context can be
          used to compute stock for arbitrary interval.
        - The key stock_assign in context can be used to compute assing move
          (in conjunction with stock_date_end equal to today).
        - If with_childs, childs locations are also computed.
        - If skip_zero, list item with quantity equal to zero are not returned.
        - If no product_ids are given the computation is done on all products.
        """
        uom_obj = self.pool.get("product.uom")
        product_obj = self.pool.get("product.product")
        rule_obj = self.pool.get('ir.rule')
        location_obj = self.pool.get('stock.location')
        date_obj = self.pool.get('ir.date')

        if not location_ids:
            return []
        if context is None:
            context= {}
        # Skip warehouse location in favor of their storage location
        # to compute quantities. Keep track of which ids to remove
        # and to add after the query.
        location_ids = set(location_ids)
        storage_to_remove = set()
        wh_to_add= {}
        for location in location_obj.browse(
            cursor, user, location_ids, context=context):
            if location.type == 'warehouse':
                location_ids.remove(location.id)
                if location.storage_location.id not in location_ids:
                    storage_to_remove.add(location.storage_location.id)
                location_ids.add(location.storage_location.id)
                wh_to_add[location.id] = location.storage_location.id
        location_ids = list(location_ids)

        move_query, move_val = rule_obj.domain_get(cursor, user, 'stock.move')

        # Assignation: filter on done until today and all asigned moves:
        if context.get('stock_assign'):
            state_date_clause = \
                '(state = %s) OR ('\
                 '(state = %s) '\
                 'AND ((effective_date IS NULL '\
                  'AND ( planned_date <= %s or planned_date IS NULL)) '\
                  'OR effective_date <= %s)'\
                ')'
            state_date_vals = ["assigned", "done",
                               context['stock_date_end'],
                               context['stock_date_end']
                               ]
        else:
            if not context.get('stock_date_end'):
                state_date_clause = "True"
                state_date_vals = []
            else:
                # date end in the past or today: filter on state done
                if context['stock_date_end'] <= date_obj.today(cursor, user,
                        context=context):
                    state_date_clause = '(state = %s) AND ('\
                        '(effective_date IS NULL '\
                         'AND ( planned_date <= %s or planned_date IS NULL)) '\
                         'OR effective_date <= %s'\
                        ')'
                    state_date_vals = ["done",
                                       context['stock_date_end'],
                                       context['stock_date_end']
                                       ]
                # infinite date end: take all states for the moves
                elif context['stock_date_end'] == datetime.date.max:
                    state_date_clause = 'state in (%s, %s, %s)'
                    state_date_vals = ['done', 'assigned', 'draft']
                # future date end: filter move on state done and date
                # before today, or on all state and date between today and
                # date_end.
                else:
                    state_date_clause = '(' + \
                        '(state in (%s)) AND ('\
                          '(effective_date IS NULL '\
                          'AND ( planned_date <= %s or planned_date IS NULL)) '\
                          'OR effective_date <= %s)' \
                        + \
                        ') OR (' + \
                         '(state in (%s, %s, %s)) AND ('\
                         '(effective_date IS NULL '\
                           'AND (( planned_date <= %s AND  planned_date > %s ) '\
                                'OR planned_date IS NULL)) '\
                           'OR (effective_date <= %s AND effective_date > %s)'\
                          ')'\
                        ')'
                    today = date_obj.today(cursor, user, context=context)
                    state_date_vals = [
                        'done', today, today,
                        'done', 'assigned', 'draft',
                        context['stock_date_end'], today,
                        context['stock_date_end'], today,
                        ]

            if context.get('stock_date_start'):
                if  context['stock_date_start'] > date_obj.today(cursor, user,
                        context=context):
                    state_date_clause += ' AND (state in (%s, %s, %s)) AND ('\
                        '(effective_date IS NULL '\
                         'AND ( planned_date >= %s or planned_date IS NULL)) '\
                         'OR effective_date >= %s'\
                        ')'
                    state_date_vals.extend(
                        ['done', 'assigned', 'draft',
                         context['stock_date_start'], context['stock_date_start']])
                else:
                    tmp_clause = '(state in (%s, %s, %s)) AND ('\
                        '(effective_date IS NULL '\
                         'AND ( planned_date >= %s or planned_date IS NULL)) '\
                         'OR effective_date >= %s'\
                        ')'
                    today = date_obj.today(cursor, user, context=context)
                    state_date_vals.extend(
                     ['done', 'assigned', 'draft', today, today])

                    state_date_clause += ' AND (' + tmp_clause + \
                        ') OR (' + \
                         '(state in (%s)) AND ('\
                         '(effective_date IS NULL '\
                           'AND (( planned_date >= %s AND  planned_date < %s ) '\
                                'OR planned_date IS NULL)) '\
                           'OR (effective_date >= %s AND effective_date < %s)'\
                          ')'\
                        ')'
                    state_date_vals.extend(
                        ['done',
                         context['stock_date_start'], today,
                         context['stock_date_start'], today,
                         ])

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

        select_clause = \
                "SELECT location, product, uom, sum(quantity) AS quantity "\
                "FROM ( "\
                    "SELECT to_location AS location, product, uom, "\
                        "sum(quantity) AS quantity "\
                    "FROM stock_move "\
                    "WHERE (%s) " \
                        "AND to_location %s "\
                    "GROUP BY to_location, product ,uom "\
                    "UNION  "\
                    "SELECT from_location AS location, product, uom, "\
                        "-sum(quantity) AS quantity "\
                    "FROM stock_move "\
                    "WHERE (%s) " \
                        "AND from_location %s "\
                    "GROUP BY from_location, product, uom "\
                ") AS T GROUP BY T.location, T.product, T.uom"

        cursor.execute(select_clause % (state_date_clause, where_clause,
                                        state_date_clause, where_clause),
                       state_date_vals + where_vals + \
                       state_date_vals + where_vals)
        raw_lines = cursor.fetchall()

        res = {}
        res_location_ids = []
        uom_ids = []
        res_product_ids = []
        for line in raw_lines:
            for id_list, position in ((res_location_ids, 0), (uom_ids, 2),
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

            # clean result
            for location, product in res.keys():
                if location not in location_ids:
                    del res[(location, product)]

        # Complete result with missing products if asked
        if not skip_zero:
            keys = ((l,p) for l in location_ids for p in product_ids)
            for location_id, product_id in keys:
                if (location_id, product_id) not in res:
                    res[(location_id, product_id)] = 0.0

        if wh_to_add:
            for wh, storage in wh_to_add.iteritems():
                for product in product_ids:
                    if (storage, product) in res:
                        res[(wh, product)] = res[(storage, product)]
                        if storage in storage_to_remove:
                            del res[(storage, product)]

        return res

    def view_header_get(self, cursor, user, value, view_type='form',
            context=None):
        if not context.get('locations'):
            return False
        location_obj = self.pool.get('stock.location')
        locations = location_obj.browse(cursor, user, context.get('locations'),
                                        context=context)
        return value + " (" + ",".join([l.name for l in locations]) + ")"

    def pick_product(self, cursor, user, move, location_quantities, context=None):
        """
        Pick the product across the location. Naive (fast)
        implementation.
        :param move is a browse record with the product and the quantity to pick.
        : param location_quantities a list of tupel (location, available_qty)
                where location is a browse record.
        """
        to_pick = []
        needed_qty = move.quantity
        for location, available_qty in location_quantities.iteritems():
            if needed_qty <= available_qty:
                to_pick.append((location, needed_qty))
                return to_pick
            else:
                to_pick.append((location, available_qty))
                needed_qty -= available_qty
        # Force assignation for consumables:
        if move.product.type == "consumable":
            to_pick.append((move.from_location.id, needed_qty))
            return to_pick
        return None

    def assign_try(self, cursor, user, moves, context=None):
        move_obj = self.pool.get('stock.move')
        product_obj = self.pool.get('product.product')
        uom_obj = self.pool.get('product.uom')
        date_obj = self.pool.get('ir.date')

        if context is None:
            context = {}

        cursor.execute('LOCK TABLE stock_move')

        local_ctx = context and context.copy() or {}
        local_ctx['stock_date_end'] = date_obj.today(cursor, user,
                context=context)
        local_ctx['stock_assign'] = True
        pbl = product_obj.products_by_location(cursor, user,
            location_ids=[m.from_location.id for m in moves],
            product_ids=[m.product.id for m in moves],
            context=local_ctx)

        success = True
        for move in moves:
            location_qties = {}
            childs = [m for m in move.from_location.childs] + [move.from_location]
            for location in childs:
                if (location.id, move.product.id) in pbl:
                    location_qties[location] = uom_obj.compute_qty(
                        cursor, user, move.product.default_uom,
                        pbl[(location.id, move.product.id)], move.uom,
                        context=context)

            to_pick = self.pick_product(
                cursor, user, move, location_qties, context=context)

            if to_pick is None:
                success = False
                continue
            first = True
            for from_location, qty in to_pick:
                to_location = move.to_location
                values = {
                    'from_location': from_location.id,
                    'to_location': to_location.id,
                    'product': move.product.id,
                    'uom': move.uom.id,
                    'quantity': qty,
                    'state': 'assigned',
                    'company': move.company.id,
                    }
                for field in ('packing_out', 'packing_in', 'packing_internal'):
                    if move[field]:
                        values.update({field: move[field].id})
                        break

                if first:
                    move_obj.write(cursor, user, move.id, values,
                            context=context)
                    first = False
                else:
                    move_obj.create(cursor, user, values, context=context)

                qty_defaut_uom = uom_obj.compute_qty(
                    cursor, user, move.uom, qty, move.product.default_uom,
                    context=context)

                pbl[(from_location.id, move.product.id)] = \
                    pbl.get((location, move.product.id), 0.0) + qty_defaut_uom
                pbl[(to_location.id, move.product.id)]= \
                    pbl.get((to_location.id, move.product.id), 0.0) - qty_defaut_uom
        return success

Product()


class ChooseStockDateInit(WizardOSV):
    _name = 'stock.product_stock_date.init'
    _description = "Compute stock quantities"
    forecast_date = fields.Date(
        'At Date', help='Allow to compute expected '\
            'stock quantities for this date.\n'\
            '* An empty value is an infinite date in the future.\n'\
            '* A date in the past will provide historical values.')

    def default_forecast_date(self, cursor, user, context=None):
        date_obj = self.pool.get('ir.date')
        return date_obj.today(cursor, user, context=context)

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
            ('inherit', '=', False),
            ], limit=1, context=context)
        model_data = model_data_obj.browse(cursor, user, model_data_ids[0],
                context=context)
        res = act_window_obj.read(cursor, user, model_data.db_id, context=context)

        if context == None: context = {}
        context['product'] = data['id']
        if data['form']['forecast_date']:
            context['stock_date_end'] = data['form']['forecast_date']
        else:
            context['stock_date_end'] = datetime.date.max
        res['context'] = str(context)

        return res

OpenLocation()
