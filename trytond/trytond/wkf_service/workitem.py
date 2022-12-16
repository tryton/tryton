#This file is part of Tryton.  The COPYRIGHT file at the top level of this repository contains the full copyright notices and license terms.
import wkf_expr
import instance

def create(cursor, act_datas, inst_id, ident, context=None):
    for act in act_datas:
        cursor.execute("SELECT NEXTVAL('wkf_workitem_id_seq')")
        (id_new,) = cursor.fetchone()
        cursor.execute("INSERT INTO wkf_workitem " \
                "(id, activity, instance, state) VALUES (%s, %s, %s, 'active')",
                (id_new, act['id'], inst_id))
        cursor.execute('SELECT * FROM wkf_workitem WHERE id=%s', (id_new,))
        res = cursor.dictfetchone()
        process(cursor, res, ident, context=context)

def process(cursor, workitem, ident, signal=None, force_running=False,
        context=None):
    cursor.execute('SELECT * FROM wkf_activity WHERE id = %s',
            (workitem['activity'],))
    activity = cursor.dictfetchone()
    triggers = False
    if workitem['state'] == 'active':
        triggers = True
        if not _execute(cursor, workitem, activity, ident, context=context):
            return False

    if workitem['state'] == 'running':
        pass

    if workitem['state'] == 'complete' or force_running:
        res = _split_test(cursor, workitem, activity['split_mode'], ident,
                signal, context=context)
        triggers = triggers and not res

    if triggers:
        cursor.execute('SELECT * FROM wkf_transition ' \
                'WHERE act_from = %s', (workitem['activity'],))
        alltrans = cursor.dictfetchall()
        for trans in alltrans:
            if trans['trigger_model']:
                ids = wkf_expr.eval_expr(cursor, ident,
                        trans['trigger_expr_id'], context=context)
                for res_id in ids:
                    cursor.execute('SELECT NEXTVAL(\'wkf_trigger_id_seq\')')
                    (new_id,) = cursor.fetchone()
                    cursor.execute('INSERT INTO wkf_trigger ' \
                            '(model, res_id, instance, workitem, id) ' \
                            'VALUES (%s, %s, %s, %s, %s)',
                            (trans['trigger_model'], res_id,
                                workitem['instance'], workitem['id'], new_id))
    return True

def _state_set(cursor, workitem, state):
    cursor.execute('UPDATE wkf_workitem ' \
            'SET state = %s WHERE id = %s', (state, workitem['id']))
    workitem['state'] = state

def _execute(cursor, workitem, activity, ident, context=None):
    "send a signal to parent workflow (signal: subflow.signal_name)"

    if (workitem['state'] == 'active') and activity['signal_send']:
        cursor.execute("SELECT i.id, w.osv, i.res_id " \
                "FROM wkf_instance i " \
                "LEFT JOIN wkf w " \
                    "ON (i.workflow = w.id) " \
                "LEFT JOIN wkf_workitem wi " \
                    "ON (i.id = wi.instance) " \
                "WHERE wi.subflow = %s)", (workitem['instance'],))
        for i in cursor.fetchall():
            instance.validate(cursor, i[0], (ident[0], i[1], i[2]),
                    activity['signal_send'], force_running=True,
                    context=context)

    if activity['kind'] == 'dummy':
        if workitem['state'] == 'active':
            _state_set(cursor, workitem, 'complete')
    elif activity['kind'] == 'function':
        if workitem['state'] == 'active':
            _state_set(cursor, workitem, 'running')
            wkf_expr.execute(cursor, ident, activity, context=context)
            _state_set(cursor, workitem, 'complete')
    elif activity['kind'] == 'stopall':
        if workitem['state'] == 'active':
            _state_set(cursor, workitem, 'running')
            cursor.execute('DELETE FROM wkf_workitem ' \
                    'WHERE instance = %s AND id <> %s',
                    (workitem['instance'], workitem['id']))
            if activity['action']:
                wkf_expr.execute(cursor, ident, activity, context=context)
            _state_set(cursor, workitem, 'complete')
    elif activity['kind'] == 'subflow':
        if workitem['state'] == 'active':
            _state_set(cursor, workitem, 'running')
            if activity.get('action', False):
                id_new = wkf_expr.execute(cursor, ident, activity,
                        context=context)
                if not (id_new):
                    cursor.execute('DELETE FROM wkf_workitem ' \
                            'WHERE id = %s', (workitem['id'],))
                    return False
                assert type(id_new) == type(1) or type(id_new) == type(1L), \
                        'Wrong return value: ' + str(id_new) + ' ' + \
                        str(type(id_new))
                cursor.execute('SELECT id FROM wkf_instance ' \
                        'WHERE res_id = %s AND workflow = %s',
                        (id_new, activity['subflow']))
                (id_new,) = cursor.fetchone()
            else:
                id_new = instance.create(cursor, ident, activity['subflow'],
                        context=context)
            cursor.execute('UPDATE wkf_workitem ' \
                    'SET subflow = %s WHERE id = %s',
                    (id_new, workitem['id']))
            workitem['subflow'] = id_new
        if workitem['state'] == 'running':
            cursor.execute("SELECT state FROM wkf_instance " \
                    "WHERE id = %s", (workitem['subflow'],))
            (state,) = cursor.fetchone()
            if state == 'complete':
                _state_set(cursor, workitem, 'complete')
    return True

def _split_test(cursor, workitem, split_mode, ident, signal=None, context=None):
    test = False
    transitions = []
    cursor.execute('SELECT * FROM wkf_transition ' \
            'WHERE act_from = %s', (workitem['activity'],))
    alltrans = cursor.dictfetchall()
    if split_mode == 'XOR' or split_mode == 'OR':
        for transition in alltrans:
            if wkf_expr.check(cursor, ident, transition, signal,
                    context=context):
                test = True
                transitions.append((transition['id'], workitem['instance']))
                if split_mode == 'XOR':
                    break
    else:
        test = True
        for transition in alltrans:
            if not wkf_expr.check(cursor, ident, transition, signal,
                    context=context):
                test = False
                break
            cursor.execute('SELECT COUNT(*) ' \
                    'FROM wkf_witm_trans WHERE trans_id = %s AND inst_id = %s',
                    (transition['id'], workitem['instance']))
            (count,) = cursor.fetchone()
            if not count:
                transitions.append((transition['id'], workitem['instance']))
    if test and len(transitions):
        cursor.executemany('INSERT INTO wkf_witm_trans ' \
                '(trans_id, inst_id) values (%s, %s)', transitions)
        cursor.execute('DELETE FROM wkf_workitem WHERE id = %s',
                (workitem['id'],))
        for transition in transitions:
            _join_test(cursor, transition[0], transition[1], ident,
                    context=context)
        return True
    return False

def _join_test(cursor, trans_id, inst_id, ident, context=None):
    cursor.execute('SELECT a.* FROM wkf_activity a ' \
                'LEFT JOIN wkf_transition t ' \
                    'ON (a.id = t.act_to) ' \
                'WHERE t.id = %s', (trans_id,))
    activity = cursor.dictfetchone()
    if activity['join_mode'] == 'XOR':
        create(cursor, [activity], inst_id, ident, context=context)
        cursor.execute('DELETE FROM wkf_witm_trans ' \
                'WHERE inst_id = %s AND trans_id = %s', (inst_id, trans_id))
    else:
        cursor.execute('SELECT id FROM wkf_transition ' \
                'WHERE act_to = %s', (activity['id'],))
        trans_ids = cursor.fetchall()
        delete = True
        for (trans_id,) in trans_ids:
            cursor.execute('SELECT COUNT(*) FROM wkf_witm_trans ' \
                    'WHERE trans_id = %s AND inst_id = %s',
                    (trans_id, inst_id))
            (count,) = cursor.fetchone()
            if not count:
                delete = False
                break
        if delete:
            for (trans_id,) in trans_ids:
                cursor.execute('DELETE FROM wkf_witm_trans ' \
                        'WHERE trans_id = %s AND inst_id = %s',
                        (trans_id, inst_id))
            create(cursor, [activity], inst_id, ident, context=context)
