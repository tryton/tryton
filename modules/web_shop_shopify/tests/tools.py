# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import time
from functools import wraps

from shopify_app import admin_graphql_request

from trytond.modules.web_shop_shopify import SHOPIFY_VERSION
from trytond.modules.web_shop_shopify.common import id2gid
from trytond.modules.web_shop_shopify.exceptions import GraphQLException


def retry(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        for _ in range(10):
            try:
                return func(*args, **kwargs)
            except Exception:
                time.sleep(1)
        return func(*args, **kwargs)
    return wrapper


def shopify_request(shop, query, variables=None, user_errors=None):
    result = admin_graphql_request(
        query=query,
        variables=variables,
        shop=shop.shopify_shop_name,
        access_token=shop.shopify_access_token,
        api_version=SHOPIFY_VERSION)
    if not result.ok:
        msg = []
        if result.log and result.log.detail:
            msg.append(result.log.detail)
        for log in result.http_logs:
            if log.detail:
                msg.append(log.detail)
        raise GraphQLException("\n".join(msg))
    if user_errors:
        names = user_errors.split('.')
        errors = result.data
        for name in names:
            errors = errors.get(name, None)
            if errors is None:
                break
        if errors:
            raise GraphQLException("\n".join(
                    f"{e['field']}: {e['message']}" for e in errors))
    return result


def get_location(shop):
    return shopify_request(shop, '''{
        locations(first:1) {
            nodes {
                id
            }
        }
    }''').data['locations']['nodes'][0]


def get_inventory_levels(shop, location):
    return shopify_request(shop, '''query InventoryLevels($id: ID!) {
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
            }).data['location']['inventoryLevels']['nodes']


def get_product(shop, id):
    return shopify_request(shop, '''query Product($id: ID!) {
        product(id: $id) {
            status
        }
    }''', {
            'id': id2gid('Product', id),
            }).data['product']


@retry
def delete_product(shop, id):
    shopify_request(shop, '''mutation productDelete($id: ID!) {
        productDelete(input: {id: $id}) {
            userErrors {
                field
                message
            }
        }
    }''', {
            'id': id,
            },
        user_errors='productDelete.userErrors')


@retry
def delete_collection(shop, id):
    shopify_request(shop, '''mutation collectionDelete($id: ID!) {
        collectionDelete(input: {id: $id}) {
            userErrors {
                field
                message
            }
        }
    }''', {
            'id': id,
            },
        user_errors='collectionDelete.userErrors')


@retry
def create_customer(shop, customer):
    return shopify_request(shop, '''mutation customerCreate(
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
            },
        user_errors='customerCreate.userErrors',
        ).data['customerCreate']['customer']


@retry
def delete_customer(shop, id):
    shopify_request(shop, '''mutation customerDelete($id: ID!) {
        customerDelete(input: {id: $id}) {
            userErrors {
                field
                message
            }
        }
    }''', {
            'id': id,
            },
        user_errors='customerDelete.userErrors')


@retry
def create_order(shop, order):
    return shopify_request(shop, '''mutation orderCreate(
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
            },
        user_errors='orderCreate.userErrors',
        ).data['orderCreate']['order']


def get_order(shop, id):
    return shopify_request(shop, '''query Order($id: ID!) {
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
            }).data['order']


@retry
def capture_order(shop, id, amount, parent_transaction_id):
    return shopify_request(shop, '''mutation orderCapture(
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
            },
        user_errors='orderCapture.userErrors',
        ).data['orderCapture']['transaction']


@retry
def delete_order(shop, id):
    shopify_request(shop, '''mutation orderDelete($orderId: ID!) {
        orderDelete(orderId: $orderId) {
            userErrors {
                field
                message
            }
        }
    }''', {
            'orderId': id,
            },
        user_errors='orderDelete.userErrors')
