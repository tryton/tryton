Marketing Email Module
######################

The marketing_email module manages mailing lists.

Mailing List
************

A mailing list groups emails under a name and a language

Email
*****

It stores emails for a mailing list and provides links to the related party or
web user.

Two actions are available:

- *Request Subscribe* which sends an e-mail to confirm the subscription to a
  list.

- *Request Unsubscribe* which sends an e-mail to confirm the unsubscription of
  an email address from the list.

Message
*******

It stores a message to send to all e-mails addresses on a list. A message is
defined by:

    * From: the address from which the message is sent.
    * List: the list of addresses to send the message to.
    * Title
    * Content
    * State:

        * Draft
        * Sending
        * Sent

A wizard is available that sends a message to a unique e-mail address from the
list for test purposes.

Configuration
*************

The marketing_email module uses parameters from the section:

- `[marketing]`:

    - `email_from`: The default `From` for the e-mails that get sent.

    - `email_subscribe_url`: the URL to confirm the subscription to which the
      parameter `token` will be added.

    - `email_unsubscribe_url`: the URL to unsubscribe an e-mail address to
      which the parameter `token` will be added.

    - `email_spy_pixel`: A boolean to activate spy pixel. Disable by default.
