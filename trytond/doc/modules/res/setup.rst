*****
Setup
*****

.. _Setting up initial users:

Setting up initial users
========================

After you have just installed Tryton, the first time that you login you will
need to use the ``admin`` account.
Once you have successfully logged in you will be presented with a configuration
wizard.
As you progress through its stages you will reach one stage that allows you to
`Configure Users <wizard-res.user.config>`.

It is often a good idea to use this opportunity to create at least one
non-administrator `User <model-res.user>`.

Nearly all of the fields can either be left blank, or already have good
default values.
You will, however, need to fill in the :guilabel:`Login` name for the new user.
It is also a good time to add some groups to the new user depending on what
they will need to access.

If you then enter in an email address you could later use the `Reset Password
<Resetting users passwords>` button to send them a temporary password.
Alternatively you can directly fill in the :guilabel:`Password` for them.

Once you have finished filling in the users details you can then click on the
:guilabel:`Add` button to save the new user account and clear the screen
ready to enter another new user.

.. tip::

   It is generally considered good practice to normally login to Tryton using
   a non-administrator account.
   The ``admin`` account is intended to be used when you need to make
   administrative changes to Tryton, such as activating new modules, or
   managing which `Groups <model-res.group>` a user belongs to.
