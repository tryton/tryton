# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.model import ModelView, ModelSQL, fields
from trytond.pool import Pool
from trytond.pyson import If, Eval


class ModelViewChangedValues(ModelView):
    'ModelView Changed Values'
    __name__ = 'test.modelview.changed_values'
    name = fields.Char('Name')
    target = fields.Many2One('test.modelview.changed_values.target', 'Target')
    stored_target = fields.Many2One(
        'test.modelview.changed_values.stored_target', "Stored Target")
    ref_target = fields.Reference('Target Reference', [
            ('test.modelview.changed_values.target', 'Target'),
            ])
    targets = fields.One2Many('test.modelview.changed_values.target', 'parent',
        'Targets')
    m2m_targets = fields.Many2Many('test.modelview.changed_values.target',
        None, None, 'Targets')


class ModelViewChangedValuesTarget(ModelView):
    'ModelView Changed Values Target'
    __name__ = 'test.modelview.changed_values.target'
    name = fields.Char('Name')
    parent = fields.Many2One('test.modelview.changed_values', 'Parent')


class ModelViewChangedValuesStoredTarget(ModelSQL):
    "ModelSQL Changed Values Target"
    __name__ = 'test.modelview.changed_values.stored_target'
    name = fields.Char("Name")


class ModelViewButton(ModelView):
    'ModelView Button'
    __name__ = 'test.modelview.button'
    value = fields.Integer("Value")

    @classmethod
    def __setup__(cls):
        super(ModelViewButton, cls).__setup__()
        cls._buttons = {
            'test': {},
            }

    @classmethod
    @ModelView.button
    def test(cls, records):
        cls.test_non_decorated(records)

    @classmethod
    def test_non_decorated(cls, records):
        pass


class ModelViewButtonDepends(ModelView):
    'ModelView Button Depends'
    __name__ = 'test.modelview.button_depends'
    value = fields.Integer("Value")

    @classmethod
    def __setup__(cls):
        super(ModelViewButtonDepends, cls).__setup__()
        cls._buttons = {
            'test': {
                'depends': ['value'],
                },
            }

    @classmethod
    @ModelView.button
    def test(cls, records):
        pass


class ModelViewButtonAction(ModelView):
    'ModelView Button Action'
    __name__ = 'test.modelview.button_action'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._buttons = {
            'test': {},
            }

    @classmethod
    @ModelView.button_action('tests.test_modelview_button_action')
    def test(cls, records):
        pass

    @classmethod
    @ModelView.button_action('tests.test_modelview_button_action')
    def test_update(cls, records):
        return {'url': 'http://www.tryton.org/'}


class ModelViewLink(ModelView):
    "ModelView Link"
    __name__ = 'test.modelview.link'


class ModelViewLinkTarget(ModelSQL):
    "ModelView Link Target"
    __name__ = 'test.modelview.link.target'


class ModelViewRPC(ModelView):
    'ModelView RPC'
    __name__ = 'test.modelview.rpc'

    selection = fields.Selection([('a', 'A')], 'Selection')
    computed_selection = fields.Selection(
        'get_selection', 'Computed Selection')
    function_selection = fields.Function(
        fields.Selection('get_function_selection', 'Function Selection'),
        'function_selection_getter')

    reference = fields.Reference('Reference', selection=[('a', 'A')])
    computed_reference = fields.Reference(
        'Computed reference', selection='get_reference')
    function_reference = fields.Function(
        fields.Reference('Function Reference',
            selection='get_function_reference'),
        'function_reference_getter')

    integer = fields.Integer('Integer')
    float = fields.Float('Float')
    char = fields.Char('Char')

    @fields.depends('selection')
    def on_change_with_integer(self):
        pass

    @fields.depends('reference')
    def on_change_float(self):
        pass

    @fields.depends('integer')
    def autocomplete_char(self):
        pass

    @classmethod
    def get_selection(cls):
        pass

    @classmethod
    def get_function_selection(cls):
        pass

    @classmethod
    def get_reference(cls):
        pass

    @classmethod
    def get_function_reference(cls):
        pass


class ModelViewEmptyPage(ModelView):
    'ModelView Empty Page'
    __name__ = 'test.modelview.empty_page'


class ModelViewCircularDepends(ModelView):
    'ModelView Circular Depends'
    __name__ = 'test.modelview.circular_depends'

    foo = fields.Char("Char", depends=['bar'])
    bar = fields.Char("Char", depends=['foobar'])
    foobar = fields.Char("Char", depends=['foo'])


class ModelViewViewAttributes(ModelView):
    'ModelView View Attributes'
    __name__ = 'test.modelview.view_attributes'

    foo = fields.Char("Char")

    @classmethod
    def view_attributes(cls):
        return super().view_attributes() + [
            ('//field[@name="foo"]',
                'visual', If(Eval('foo') == 'foo', 'danger', '')),
            ]


class ModelViewViewAttributesDepends(ModelView):
    'ModelView View Attributes Depends'
    __name__ = 'test.modelview.view_attributes_depends'

    foo = fields.Char("Char")
    bar = fields.Char("Char")

    @classmethod
    def view_attributes(cls):
        return super().view_attributes() + [
            ('//field[@name="foo"]',
                'visual', If(Eval('bar') == 'foo', 'danger', ''), ['bar']),
            ]


def register(module):
    Pool.register(
        ModelViewChangedValues,
        ModelViewChangedValuesTarget,
        ModelViewChangedValuesStoredTarget,
        ModelViewButton,
        ModelViewButtonDepends,
        ModelViewButtonAction,
        ModelViewLink,
        ModelViewLinkTarget,
        ModelViewRPC,
        ModelViewEmptyPage,
        ModelViewCircularDepends,
        ModelViewViewAttributes,
        ModelViewViewAttributesDepends,
        module=module, type_='model')
