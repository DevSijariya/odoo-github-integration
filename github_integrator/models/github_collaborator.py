from odoo import fields, models


class GitHubCollaborator(models.Model):
    _name = "github.collaborator"
    _description = "GitHub Collaborator"

    login = fields.Char(string="Login", required=True)
    name = fields.Char(string="Name")
    profile_url = fields.Char(string="Profile URL")
    is_admin = fields.Boolean(string="Admin")
    can_push = fields.Boolean(string="Can Push")
    can_pull = fields.Boolean(string="Can Pull")
    repository_id = fields.Many2one(
        "github.repository",
        string="Repository",
        required=True,
        ondelete="cascade",
    )

    _sql_constraints = [
        (
            "unique_collaborator_per_repository",
            "unique(repository_id, login)",
            "Collaborator already exists for this repository.",
        )
    ]
