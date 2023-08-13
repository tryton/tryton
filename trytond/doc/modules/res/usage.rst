*****
Usage
*****

.. _Updating your preferences:

Updating your preferences
=========================

Some of the properties of your `User <model-res.user>` account can be viewed
and updated by opening up your preferences.

How you open your preferences depends on which client you are using, but it is
often done from either a menu item called preferences, or a link somewhere in
the header with your username.

With your preferences open you are able to update things like your name, email
address, language, signature and password.

.. _Connecting user applications:

Connecting user applications
============================

Tryton `User Applications <topics-user_application>` are intended to be simple
applications that have been written to do one thing well.

When you configure the user application it connects to Tryton and requests a
new key.
This new key is stored in the associated `User's list of Applications
<model-res.user.application>`.

To allow the user application to access and use Tryton you must
:guilabel:`Validate` the key from inside `your preferences <Updating your
preferences>`.
Once this is done the user application can perform it's predefined actions on
your behalf.

.. tip::

   If you are concerned a key may have been compromised, you can easily
   revoke a user application's access, at any time, by deleting its key
   from your user preferences.

.. _Managing user's access rights:

Managing users access rights
============================

In Tryton `Groups <model-res.group>` help you manage and control what `Access
Rights <topics-access_rights>` a `User <model-res.user>` has.

By adding and removing users from groups you can control what parts of Tryton a
user can access, and what they can see and do.
You can find the users and groups under the
[:menuselection:`Administration --> Users`] main menu item.

If you want to see and change which users are in a group, then it is normally
best to open the group to view it's members.

If you are interested in seeing and updating which groups a single user belongs
to, then it is often best to open the user account and then find their access
permissions and groups.

.. tip::

   Many modules define standard groups that are useful to people who have
   activated that module.
   Often you only need to add the correct users to these groups to benefit from
   them.

.. _Resetting users passwords:

Resetting users passwords
=========================

If a user has forgotten their password, or you are creating a new user and want
them to set their password themselves, Tryton can send them a temporary
password.
On the User screen there is a :guilabel:`Reset Password` button which will send
them an `Email Reset Password <report-res.user.email_reset_password>` email to
their email address.

.. note::

   This is only available if the email address for the user is set.

The user can then login with this temporary password and update their password
to one of their choosing.

.. note::

   The temporary password is only valid for a set amount of time, so the user
   must login and change their password before the temporary password expires.
