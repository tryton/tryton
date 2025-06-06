==================
User Role Scenario
==================

Imports::

    >>> import datetime as dt

    >>> from proteus import Model
    >>> from trytond.tests.tools import activate_modules, assertEqual

Activate modules::

    >>> config = activate_modules('user_role')

Create some groups::

    >>> Group = Model.get('res.group')
    >>> groups = [Group(name="Group %s" % i) for i in range(5)]
    >>> Group.save(groups)

Create a role::

    >>> Role = Model.get('res.role')
    >>> role = Role(name="Role")
    >>> role.groups.append(Group(groups[0].id))
    >>> role.groups.append(Group(groups[1].id))
    >>> role.save()

Create a user with some groups::

    >>> User = Model.get('res.user')
    >>> user = User(login="user")
    >>> user.groups.append(Group(groups[1].id))
    >>> user.groups.append(Group(groups[2].id))
    >>> user.groups.append(Group(groups[3].id))
    >>> user.save()
    >>> len(user.groups)
    3

Set the role to the user::

    >>> user_role = user.roles.new()
    >>> user_role.role = role
    >>> user.save()

    >>> len(user.groups)
    2
    >>> assertEqual(user.groups, [groups[0], groups[1]])

Start the role in the future::

    >>> user_role, = user.roles
    >>> user_role.from_date = dt.datetime.now() + dt.timedelta(days=1)
    >>> user_role.to_date = None
    >>> user.save()

    >>> len(user.groups)
    0

End the role in the past::

    >>> user_role, = user.roles
    >>> user_role.from_date = None
    >>> user_role.to_date = dt.datetime.now() - dt.timedelta(days=1)
    >>> user.save()

    >>> len(user.groups)
    0

Start the role in the past and end in the future::

    >>> user_role, = user.roles
    >>> user_role.from_date = dt.datetime.now() - dt.timedelta(days=1)
    >>> user_role.to_date = dt.datetime.now() + dt.timedelta(days=1)
    >>> user.save()

    >>> len(user.groups)
    2

Changing groups to role::

    >>> role.groups.append(Group(groups[4].id))
    >>> role.save()

    >>> user.reload()
    >>> len(user.groups)
    3

Deleting role::

    >>> role.delete()

    >>> user.reload()
    >>> len(user.groups)
    0
