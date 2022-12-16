.. _ref-wizard:
.. module:: trytond.wizard

======
Wizard
======

A wizard is a `finite state machine`_.

There is also a more :ref:`practical introduction into wizards
<topics-wizard>`.

.. _`finite state machine`: http://en.wikipedia.org/wiki/Finite-state_machine

.. class:: Wizard(session_id)

    This is the base for any wizard. It contains the engine for the finite
    state machine. A wizard must have some :class:`State` instance attributes
    that the engine will use.

Class attributes are:

.. attribute:: Wizard.__name__

    It contains the unique name to reference the wizard throughout the
    platform.

.. attribute:: Wizard.start_state

    It contains the name of the starting state.

.. attribute:: Wizard.end_state

    It contains the name of the ending state.
    If an instance method with this name exists on the wizard, it will be
    called on deletion of the wizard and it may return one of the :ref:`client
    side action keywords <topics-views-client-actions>`.

.. attribute:: Wizard.__rpc__

    Same as :attr:`trytond.model.Model.__rpc__`.

.. attribute:: Wizard.states

    It contains a dictionary with state name as key and :class:`State` as
    value.

Class methods are:

.. classmethod:: Wizard.__setup__()

    Setup the class before adding into the :class:`trytond.pool.Pool`.

.. classmethod:: Wizard.__post_setup__()

    Setup the class after added into the :class:`trytond.pool.Pool`.

.. classmethod:: Wizard.__register__(module_name)

    Register the wizard.

.. classmethod:: Wizard.create()

    Create a session for the wizard and returns a tuple containing the session
    id, the starting and ending state.

.. classmethod:: Wizard.delete(session_id)

    Delete the session.

.. classmethod:: Wizard.execute(session_id, data, state_name)

    Execute the wizard for the state.
    `session_id` is a session id.
    `data` is a dictionary with the session data to update.
    `active_id`, `active_ids`, `active_model` and `action_id` must be set in
    the context according to the records on which the wizard is run.

=====
State
=====

.. class:: State()

    This is the base for any wizard state.

Instance attributes are:

.. attribute:: State.name

    The name of the state.

=========
StateView
=========

.. class:: StateView(model_name, view, buttons)

    A :class:`StateView` is a state that will display a form in the client.
    The form is defined by the :class:`~trytond.model.ModelView` with the name
    `model_name`, the `XML` id in `view` and the `buttons`.
    The default value of the view can be set with a method on wizard having the
    same name as the state but starting with `default_`.

Instance attributes are:

.. attribute:: StateView.model_name

    The name of the :class:`~trytond.model.ModelView`.

.. attribute:: StateView.view

    The `XML` id of the form view.

.. attribute:: StateView.buttons

    The list of :class:`Button` instances to display on the form.

Instance methods are:

.. method:: StateView.get_view(wizard, state_name)

    Returns the view definition like
    :meth:`~trytond.model.ModelView.fields_view_get`.

    * wizard is a :class:`Wizard` instance
    * state_name is the name of the :class:`StateView` instance

.. method:: StateView.get_defaults(wizard, state_name, fields)

    Return default values for the fields.

    * wizard is a :class:`Wizard` instance
    * state_name is the name of the :class:`State`
    * fields is the list of field names

.. method:: StateView.get_buttons(wizard, state_name)

    Returns button definitions of the wizard.

    * wizard is a :class:`Wizard` instance
    * state_name is the name of the :class:`StateView` instance

===============
StateTransition
===============

.. class:: StateTransition()

    A :class:`StateTransition` brings the wizard to the `state` returned by the
    method having the same name as the state but starting with `transition_`.

===========
StateAction
===========

.. class:: StateAction(action_id)

    A :class:`StateAction` is a :class:`StateTransition` which let the client
    launch an `ir.action`. This action definition can be customized with a
    method on wizard having the same name as the state but starting with `do_`.

Instance attributes are:

.. attribute:: StateAction.action_id

    The `XML` id of the `ir.action`.

Instance methods are:

.. method:: StateAction.get_action()

    Returns the `ir.action` definition.

===========
StateReport
===========

.. class:: StateReport(report_name)

    A :class:`StateReport` is a :class:`StateAction` which find the report
    action by name instead of `XML` id.

======
Button
======

.. class:: Button(string, state[, icon[, default]])

    A :class:`Button` is a single object containing the definition of a wizard
    button.

Instance attributes are:

.. attribute:: Button.string

    The label display on the button.

.. attribute:: Button.state

    The next state to reach if button is clicked.

.. attribute:: Button.icon

    The name of the icon to display on the button.

.. attribute:: Button.default

    A boolean to set it as default on the form.
