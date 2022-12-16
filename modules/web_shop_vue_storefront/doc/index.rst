Web Vue Storefront Module
#########################

The web_shop_vue_storefront module provides the back-end to integrate with `Vue
Storefront`_ 1.x.

.. _`Vue Storefront`: https://www.vuestorefront.io/


Vue StoreFront Configuration
----------------------------

The endpoint must be updated to use the Tryton URL. You must just replace
`/api` by
`http(s)://<hostname>:<port>/<database name>/web_shop_vue_storefront/<shop name>`.

The configuration `autoRefreshTokens` must be set to `false`.
