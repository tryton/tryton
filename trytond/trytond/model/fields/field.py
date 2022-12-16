#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.


class Field(object):
    _type = None

    def __init__(self, string='', help='', required=False, readonly=False,
            domain=None, states=None, priority=0, change_default=False,
            translate=False, select=0, on_change=None, on_change_with=None,
            depends=None, order_field=None, context=None):
        '''
        :param string: A string for label of the field.
        :param help: A multi-line help string.
        :param required: A boolean if ``True`` the field is required.
        :param readonly: A boolean if ``True`` the field is not editable in
            the user interface.
        :param domain: A list that defines a domain constraint. See domain on
            ModelStorage.search.
        :param states: A dictionary. Possible keys are ``required``,
            ``readonly`` and ``invisible``. Values are strings of python
            statements that can be evaluated with record values. This allows to
            change dynamically the attributes of the field.
        :param priority: Give the order in which set methods are called.
        :param change_default: A boolean. If ``True`` the field can be used as
        condition for a custom default value.
        :param translate: A boolean. If ``True`` the field is translatable.
        :param select: An integer. When equal to ``1``, the field appears in the
            search box in list view and the search will be optimized. When equal to
            ``2`` the field appears in the *Advanced Search* in the search box.
        :param on_change: A list of values. If set, the client will call the
            method ``on_change_<field_name>`` when the user changes the field
            value. It then passes this list of values as arguments to the
            function.
        :param on_change_with: A list of values. Like ``on_change``, but defined
            the other way around. The list contains all the fields that must
            update the current field.
        :param depends: A list of field name on which this one depends.
        :param order_field: A string. If set it will use the string when
            ordering records on the field.
        :param context: A string defining a dictionary which will be given
            to open the relation fields.
        '''
        self.string = string
        self.help = help
        self.required = required
        self.readonly = readonly
        self.domain = domain or []
        assert isinstance(self.domain, list), 'domain must be a list'
        self.states = states or {}
        self.priority = priority
        self.change_default = change_default
        self.translate = translate
        self.select = select
        self.on_change = on_change
        self.on_change_with = on_change_with
        self.depends = depends or []
        self.order_field = order_field
        self.context = context or ''
