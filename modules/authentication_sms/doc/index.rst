Authentication SMS Module
#########################

The `SMS <https://en.wikipedia.org/wiki/Short_Message_Service>`_ authentication
module allows to authenticate users via SMS.  There are two authentication
methods `sms` and `password_sms` which can be used in the `authentications`
list of the `session` section in the configuration.

The `sms` method just send a code via SMS to the user. Then the user needs to
transcribe the code into the login dialog.

The `password_sms` method send a code only after the user entered a valid
password. This provides a `two-factor authentication
<https://en.wikipedia.org/wiki/Two-factor_authentication>`_ method.

Both methods require that the user has a *Mobile* phone number defined
otherwise he can not be authenticated with those methods.

Configuration
*************

The configuration of the module is set in the `authentication_sms` section.

function
--------

The fully qualified name of the method to send SMS. It must take three
arguments: text, to and from.
This method is required to send SMS.

from
----

The number from which the SMS are sent.

length
------

The length of the generated code.
Default: 6

ttl
---

The time to live for the generated codes in seconds.
Default: 300

name
----

The name used in the SMS text.
Default: Tryton
