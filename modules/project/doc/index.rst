Project Module
##############

The Project module provides the concepts of project and task and the
basis for simple project management.


Work Effort
***********

The Work Effort model is used for creating both projects and tasks. This allows
for instance to transform a task into a project if it gets bigger and need to
be split. The following fields are defined on the model:


- Name: The name of the Project/Task.
- Work: The linked timesheet work.
- Type: Can be *Project* or *Task*.
- State: Can be *Opened* or *Done*.
- Parent and Children: Define the tree structure of projects and
  tasks.
- Party and Party Address: The optional party (and the contact
  address) for which the project is made. Available on projects.
- Effort: The estimated effort of a task.
- Total Effort: Available on projects. Gives the total effort of the
  sub-tasks (I.E. tasks of the project and tasks of the sub-projects)
  of the current project.
- Progress: The progression on the task.
- Total Progress: Gives the total of progress of the sub-tasks.
- Comment: A description.
