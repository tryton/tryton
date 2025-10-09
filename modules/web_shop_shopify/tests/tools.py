# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import shopify

from trytond.modules.web_shop_shopify.common import id2gid
from trytond.modules.web_shop_shopify.shopify_retry import GraphQLException


def get_location():
    return shopify.GraphQL().execute('''{
        locations(first:1) {
            nodes {
                id
            }
        }
    }''')['data']['locations']['nodes'][0]


def get_inventory_levels(location):
    return shopify.GraphQL().execute('''query InventoryLevels($id: ID!) {
        location(id: $id) {
            inventoryLevels(first: 250) {
                nodes {
                    item {
                        id
                    }
                    quantities(names: ["available"]) {
                        name
                        quantity
                    }
                }
            }
        }
    }''', {
            'id': location['id'],
            })['data']['location']['inventoryLevels']['nodes']


def get_product(id):
    return shopify.GraphQL().execute('''query Product($id: ID!) {
        product(id: $id) {
            status
        }
    }''', {
            'id': id2gid('Product', id),
            })['data']['product']


def delete_product(id):
    result = shopify.GraphQL().execute('''mutation productDelete($id: ID!) {
        productDelete(input: {id: $id}) {
            userErrors {
                field
                message
            }
        }
    }''', {
            'id': id,
            })['data']['productDelete']
    if errors := result.get('userErrors'):
        raise GraphQLException({'errors': errors})


def delete_collection(id):
    result = shopify.GraphQL().execute('''mutation collectionDelete($id: ID!) {
        collectionDelete(input: {id: $id}) {
            userErrors {
                field
                message
            }
        }
    }''', {
            'id': id,
            })['data']['collectionDelete']
    if errors := result.get('userErrors'):
        raise GraphQLException({'errors': errors})


def create_customer(customer):
    result = shopify.GraphQL().execute('''mutation customerCreate(
    $input: CustomerInput!) {
        customerCreate(input: $input) {
            customer {
                id
            }
            userErrors {
                field
                message
            }
        }
    }''', {
            'input': customer,
            })['data']['customerCreate']
    if errors := result.get('userErrors'):
        raise GraphQLException({'errors': errors})
    return result['customer']


def delete_customer(id):
    result = shopify.GraphQL().execute('''mutation customerDelete($id: ID!) {
        customerDelete(input: {id: $id}) {
            userErrors {
                field
                message
            }
        }
    }''', {
            'id': id,
            })['data']['customerDelete']
    if errors := result.get('userErrors'):
        raise GraphQLException({'errors': errors})


def create_order(order):
    result = shopify.GraphQL().execute('''mutation orderCreate(
    $order: OrderCreateOrderInput!) {
        orderCreate(order: $order) {
            order {
                id
                totalPriceSet {
                    presentmentMoney {
                        amount
                        currencyCode
                    }
                }
                displayFinancialStatus
                displayFulfillmentStatus
                transactions(first: 250) {
                    id
                }
                fulfillments {
                    id
                }
                closed
            }
            userErrors {
                field
                message
            }
        }
    }''', {
            'order': order,
            })['data']['orderCreate']
    if errors := result.get('userErrors'):
        raise GraphQLException({'errors': errors})
    return result['order']


def get_order(id):
    return shopify.GraphQL().execute('''query Order($id: ID!) {
        order(id: $id) {
            id
            totalPriceSet {
                presentmentMoney {
                    amount
                    currencyCode
                }
            }
            displayFinancialStatus
            displayFulfillmentStatus
            transactions(first: 250) {
                id
            }
            fulfillments {
                id
                fulfillmentLineItems(first: 10) {
                    nodes {
                        quantity
                    }
                }
            }
            closed
        }
    }''', {
            'id': id,
            })['data']['order']


def capture_order(id, amount, parent_transaction_id):
    result = shopify.GraphQL().execute('''mutation orderCapture(
    $input: OrderCaptureInput!) {
        orderCapture(input: $input) {
            transaction {
                id
            }
            userErrors {
                field
                message
            }
        }
    }''', {
            'input': {
                'amount': amount,
                'id': id,
                'parentTransactionId': parent_transaction_id,
                },
            })['data']['orderCapture']
    if errors := result.get('userErrors'):
        raise GraphQLException({'errors': errors})
    return result['transaction']


def delete_order(id):
    result = shopify.GraphQL().execute('''mutation orderDelete($orderId: ID!) {
        orderDelete(orderId: $orderId) {
            userErrors {
                field
                message
            }
        }
    }''', {
            'orderId': id,
            })['data']['orderDelete']
    if errors := result.get('userErrors'):
        raise GraphQLException({'errors': errors})
