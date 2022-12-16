Stock Lot Shelf Life Expiration Date
####################################

The stock_lot_sled module adds two fields on lot of products:

    - Shelf Live Expiration Date
    - Expiration Date

And it defines on the product the default time for those fields and on the
stock configuration the Shelf Live Delay.

When the shelf life of a lot expires in less than the configured shelf life
delay, it is no more used to compute the forecast quantity of the stock.
