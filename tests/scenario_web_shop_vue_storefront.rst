================================
Web Shop Vue Storefront Scenario
================================

Imports::

    >>> from decimal import Decimal
    >>> from unittest.mock import MagicMock, ANY

    >>> from proteus import Model
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import (
    ...     create_company, get_company)
    >>> from trytond.modules.account.tests.tools import (
    ...     create_chart, get_accounts)

    >>> from trytond.modules.web_shop_vue_storefront.tests.tools import (
    ...     AnyDictWith)

Patch elasticsearch::

    >>> from trytond.modules.web_shop_vue_storefront import web
    >>> es = MagicMock()
    >>> web.VSFElasticsearch = MagicMock(return_value=es)

Install web_shop_vue_storefront::

    >>> config = activate_modules(
    ...     ['web_shop_vue_storefront', 'product_attribute'])

Create company::

    >>> Company = Model.get('company.company')
    >>> _ = create_company()
    >>> company = get_company()

Create chart of accounts::

    >>> _ = create_chart(company)
    >>> accounts = get_accounts(company)

Define a web shop::

    >>> WebShop = Model.get('web.shop')
    >>> web_shop = WebShop(name="Web Shop")
    >>> web_shop.type = 'vsf'
    >>> web_shop.save()

Create categories::

    >>> Category = Model.get('product.category')
    >>> category1 = Category(name="Category 1")
    >>> category1.save()
    >>> sub_category = Category(name="Sub Category", parent=category1)
    >>> sub_category.save()
    >>> category2 = Category(name="Category 2")
    >>> category2.save()

    >>> account_category = Category(name="Account Category")
    >>> account_category.accounting = True
    >>> account_category.account_expense = accounts['expense']
    >>> account_category.account_revenue = accounts['revenue']
    >>> account_category.save()

Create attribute set::

    >>> ProductAttributeSet = Model.get('product.attribute.set')
    >>> ProductAttribute = Model.get('product.attribute')
    >>> attribute_set = ProductAttributeSet(name="Attributes")
    >>> attribute = attribute_set.attributes.new()
    >>> attribute.name = 'attr1'
    >>> attribute.string = "Attribute 1"
    >>> attribute.type_ = 'selection'
    >>> attribute.selection = "opt1:Option1\nopt2:Option2"
    >>> attribute = attribute_set.attributes.new()
    >>> attribute.name = 'attr2'
    >>> attribute.string = "Attribute 1"
    >>> attribute.type_ = 'boolean'
    >>> attribute_set.save()
    >>> attribute1, attribute2 = attribute_set.attributes

Create products::

    >>> ProductUom = Model.get('product.uom')
    >>> unit, = ProductUom.find([('name', '=', 'Unit')])
    >>> ProductTemplate = Model.get('product.template')
    >>> Product = Model.get('product.product')
    >>> template = ProductTemplate()
    >>> template.name = "Product 1"
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.salable = True
    >>> template.list_price = Decimal(10)
    >>> template.account_category = account_category
    >>> template.categories.append(Category(category1.id))
    >>> template.categories.append(Category(sub_category.id))
    >>> template.save()
    >>> product1, = template.products
    >>> product1.suffix_code = 'PROD1'
    >>> product1.save()

    >>> template = ProductTemplate()
    >>> template.name = "Product 2"
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.salable = True
    >>> template.list_price = Decimal(20)
    >>> template.account_category = account_category
    >>> template.save()
    >>> product2, = template.products
    >>> product2.suffix_code = 'PROD2'
    >>> product2.save()

    >>> configurable = ProductTemplate()
    >>> configurable.name = "Configurable"
    >>> configurable.code = "CONF"
    >>> configurable.default_uom = unit
    >>> configurable.type = 'goods'
    >>> configurable.salable = True
    >>> configurable.list_price = Decimal(50)
    >>> configurable.attribute_set = attribute_set
    >>> configurable.account_category = account_category
    >>> configurable1, = configurable.products
    >>> configurable1.suffix_code = "1"
    >>> configurable1.attributes = {
    ...     'attr1': 'opt1',
    ...     'attr2': True,
    ...     }
    >>> configurable2 = configurable.products.new()
    >>> configurable2.suffix_code = "2"
    >>> configurable2.attributes = {
    ...     'attr1': 'opt2',
    ...     'attr2': True,
    ...     }
    >>> configurable.save()
    >>> configurable1, configurable2 = configurable.products

Set categories, products and attributes to web shop::

    >>> web_shop.categories.extend([
    ...         Category(category1.id),
    ...         Category(sub_category.id),
    ...         Category(category2.id)])
    >>> web_shop.products.extend([
    ...         Product(product1.id),
    ...         Product(product2.id),
    ...         Product(configurable1.id),
    ...         Product(configurable2.id)])
    >>> web_shop.attributes.extend([
    ...         ProductAttribute(attribute1.id),
    ...         ProductAttribute(attribute2.id)])
    >>> web_shop.save()

Run VSF update::

    >>> es.reset_mock()
    >>> Cron = Model.get('ir.cron')
    >>> cron_sync, = Cron.find([
    ...     ('method', '=', 'web.shop|vsf_update'),
    ...     ])
    >>> cron_sync.click('run_once')
    >>> es.index.call_count
    8
    >>> es.index.assert_any_call(
    ...     id=category1.vsf_identifier.id, index='vue_storefront_catalog',
    ...     doc_type='category', body=AnyDictWith({
    ...         'name': "Category 1",
    ...         'parent_id': None,
    ...         'url_key': 'category-1',
    ...         'url_path': 'category-1',
    ...         'level': 1,
    ...         'product_count': 1,
    ...         'children_data': [AnyDictWith({})],
    ...         }))
    >>> es.index.assert_any_call(
    ...     id=sub_category.vsf_identifier.id, index='vue_storefront_catalog',
    ...     doc_type='category', body=AnyDictWith({
    ...         'name': "Sub Category",
    ...         'parent_id': category1.vsf_identifier.id,
    ...         'url_key': 'sub-category',
    ...         'url_path': 'category-1/sub-category',
    ...         'level': 2,
    ...         'product_count': 1,
    ...         'children_data': [],
    ...         }))
    >>> es.index.assert_any_call(
    ...     id=product1.vsf_identifier.id, index='vue_storefront_catalog',
    ...     doc_type='product', body=AnyDictWith({
    ...         'name': "Product 1",
    ...         'image': '/product/prod1.jpg',
    ...         'sku': 'PROD1',
    ...         'url_key': 'product-1',
    ...         'type_id': 'simple',
    ...         'price': 10,
    ...         'price_tax': 0,
    ...         'price_incl_tax': 10,
    ...         'status': 3,
    ...         'category_ids': [ANY, ANY],
    ...         'category': [AnyDictWith({}), AnyDictWith({})],
    ...         'stock': [{
    ...                 'is_in_stock': False,
    ...                 'qty': 0,
    ...                 }],
    ...         }))
    >>> es.index.assert_any_call(
    ...     id=configurable.vsf_identifier.id, index='vue_storefront_catalog',
    ...     doc_type='product', body=AnyDictWith({
    ...         'name': "Configurable",
    ...         'image': '/product/conf.jpg',
    ...         'sku': 'CONF',
    ...         'url_key': 'configurable',
    ...         'type_id': 'configurable',
    ...         'price': 50,
    ...         'price_tax': 0,
    ...         'price_incl_tax': 50,
    ...         'status': 3,
    ...         'category_ids': [],
    ...         'category': [],
    ...         'stock': [{
    ...                 'is_in_stock': False,
    ...                 'qty': 0,
    ...                 }],
    ...         'attr1_options': [1, 2],
    ...         'attr2_options': [],
    ...         'configurable_options': [
    ...             AnyDictWith({
    ...                     'attribute_code': 'attr1',
    ...                     'label': "Attribute 1",
    ...                     'product_id': configurable.vsf_identifier.id,
    ...                     'values': [
    ...                         {'value_index': 1, 'label': "Option1"},
    ...                         {'value_index': 2, 'label': "Option2"},
    ...                         ],
    ...                     }),
    ...             AnyDictWith({}),
    ...             ],
    ...         'configurable_children': [
    ...             AnyDictWith({'sku': 'CONF1'}),
    ...             AnyDictWith({'sku': 'CONF2'}),
    ...             ],
    ...         }))
    >>> es.index.assert_any_call(
    ...     id=attribute1.vsf_identifier.id, index='vue_storefront_catalog',
    ...     doc_type='attribute', body=AnyDictWith({
    ...         'attribute_code': 'attr1',
    ...         'frontend_input': 'selection',
    ...         'frontend_label': "Attribute 1",
    ...         'options': [
    ...             {'value': 1, 'name': 'opt1', 'label': "Option1"},
    ...             {'value': 2, 'name': 'opt2', 'label': "Option2"},
    ...             ],
    ...         }))

Remove a category, a product and an attribute::

    >>> _ = web_shop.categories.pop(web_shop.categories.index(category2))
    >>> _ = web_shop.products.pop(web_shop.products.index(product2))
    >>> _ = web_shop.attributes.pop(web_shop.attributes.index(attribute2))
    >>> web_shop.save()

Run VSF update::

    >>> es.reset_mock()
    >>> Cron = Model.get('ir.cron')
    >>> cron_sync, = Cron.find([
    ...     ('method', '=', 'web.shop|vsf_update'),
    ...     ])
    >>> cron_sync.click('run_once')
    >>> es.index.call_count
    5
    >>> es.delete.call_count
    3
