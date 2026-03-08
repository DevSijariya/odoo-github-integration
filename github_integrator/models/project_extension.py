from odoo import fields, models


class ProjectProject(models.Model):
    _inherit = "project.project"

    github_repository_id = fields.Many2one(
        "github.repository",
        string="GitHub Repository",
        ondelete="set null",
    )


class ProjectTask(models.Model):
    _inherit = "project.task"

    github_issue_id = fields.Many2one(
        "github.issue",
        string="GitHub Issue",
        ondelete="set null",
    )
