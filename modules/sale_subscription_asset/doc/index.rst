Sale Subscription Asset Module
##############################

The sale subscription asset module adds the notion of asset to the sale
subscription module.

Two fields are added to the *Service*:

    - *Lots*: All the lots that can be used when providing this service
    - *Available Lots*: A subset of the preceding field displaying the
      available lots

On the *Subscription Line*, it is possible to specify the lot to use. When the
subscription will be running this field will become required for service with
lots.

On the *Lot*, the field *Subscribed* will point to the line of the subscription
currently using this lot.
