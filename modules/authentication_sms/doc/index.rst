Authentication SMS Module
#########################

The `SMS <https://en.wikipedia.org/wiki/Short_Message_Service>`_ authentication
module allows users to authenticate via SMS.  It adds a new authentication
method `sms`, which can be used in the list of `authentications` in the
`session` section of the configuration file.

The `sms` method just sends a code via SMS to the user. Then the user needs to
transcribe the code into the login dialog.

This method requires that the user has the correct *Mobile* phone number
defined otherwise it will not be possible for them to authenticate.

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
