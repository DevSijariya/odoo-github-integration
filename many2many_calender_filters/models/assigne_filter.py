from odoo import models, fields, api

class ProjectTask(models.Model):
    _inherit = 'project.task'

    assignee_id = fields.Many2one('res.users', string='Assignee', index=True)


class ProjectCalendarFilters(models.Model):
    _name = 'project.calendar.filters'
    _description = 'Project Calendar Filters'

    user_id = fields.Many2one('res.users', required=True, ondelete='cascade')

    project_id = fields.Many2one(
        'project.project',
        index=True
    )

    assignee_id = fields.Many2one(
        'res.users',
        index=True
    )

    project_checked = fields.Boolean(default=True)
    assignee_checked = fields.Boolean(default=True)

    active = fields.Boolean(default=True)

    _sql_constraints = [
        (
            'unique_project_per_user',
            'UNIQUE(user_id, project_id)',
            'Project filter already exists.'
        )
    ]

    def write(self, vals):
        res = super().write(vals)
        if 'project_checked' in vals:
            self.env['project.assignee.filters']._sync_assignees_with_projects()
        return res


    @api.model
    def create(self, vals):
        rec = super().create(vals)
        # Only sync if the project filter is enabled
        if vals.get('project_checked', True):
            self.env['project.assignee.filters']._sync_assignees_with_projects()
        return rec


    def unlink(self):
        res = super().unlink()
        self.env['project.assignee.filters']._sync_assignees_with_projects()
        return res


class ProjectAssigneeFilters(models.Model):
    _name = 'project.assignee.filters'
    _description = 'Project Assignee Calendar Filters'

    user_id = fields.Many2one('res.users', 'Me', required=True,  index=True, ondelete='cascade')
    assignee_id = fields.Many2one('res.users', 'Assignee', required=True, index=True)
    active = fields.Boolean('Active', default=True)
    assignee_checked = fields.Boolean('Checked', default=True)

    _sql_constraints = [
        ('user_id_assignee_id_unique', 'UNIQUE(user_id, assignee_id)', 'A user cannot have the same assignee twice.')
    ]

    @api.model
    def unlink_from_assignee_id(self, assignee_id):
        return self.search([('assignee_id', '=', assignee_id)]).unlink()

    @api.model
    def _sync_assignees_with_projects(self):
        user = self.env.user

        # enabled project filters
        project_filters = self.env['project.calendar.filters'].search([
            ('user_id', '=', user.id),
            ('project_checked', '=', True),
            ('project_id', '!=', False),
        ])

        projects = project_filters.mapped('project_id')

        # no project selected → remove all assignees
        if not projects:
            self.search([('user_id', '=', user.id)]).unlink()
            return

        # get tasks from selected projects
        tasks = self.env['project.task'].search([
            ('project_id', 'in', projects.ids),
            ('user_ids', '!=', False),
        ])

        # collect assignees (Many2many!)
        assignees = tasks.mapped('user_ids')

        # remove obsolete assignee filters
        self.search([
            ('user_id', '=', user.id),
            ('assignee_id', 'not in', assignees.ids),
        ]).unlink()

        # existing assignees
        existing = self.search([
            ('user_id', '=', user.id),
        ]).mapped('assignee_id').ids
        existing.append(user.id)
        # create missing assignee filters
        for assignee in assignees:
            if assignee.id not in existing:
                self.create({
                    'user_id': user.id,
                    'assignee_id': assignee.id,
                    'assignee_checked': True,
                })
