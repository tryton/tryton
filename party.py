from trytond.wizard import Wizard

class OpenSupplier(Wizard):
    'Open Suppliers'
    _name = 'relationship.party.open_supplier'
    states = {
        'init': {
            'result': {
                'type': 'action',
                'action': '_action_open',
                'state': 'end',
            },
        },
    }

    def _action_open(self, cursor, user, datas, context=None):
        model_data_obj = self.pool.get('ir.model.data')
        act_window_obj = self.pool.get('ir.action.act_window')

        model_data_ids = model_data_obj.search(cursor, user, [
                ('fs_id', '=', 'act_party_form'),
                ('module', '=', 'relationship'),
                ], limit=1, context=context)
        model_data = model_data_obj.browse(cursor, user, model_data_ids[0],
                                           context=context)
        res = act_window_obj.read(cursor, user, model_data.db_id,
                                  context=context)
        cursor.execute(
            "SELECT party, max(purchase_date) FROM purchase_purchase "\
                "GROUP BY party "\
                "ORDER BY max(purchase_date) DESC"
            )
        suppliers = [line[0] for line in cursor.fetchall()]

        domain = eval( res.get('domain') or "[]" )
        domain.append(('id', 'in', suppliers))
        res['domain'] = str(domain)
        return res

OpenSupplier()
