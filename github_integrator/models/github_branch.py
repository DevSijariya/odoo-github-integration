from odoo import fields, models


class GitHubBranch(models.Model):
    _name = "github.branch"
    _description = "GitHub Branch"

    name = fields.Char(string="Branch Name", required=True)
    repository_id = fields.Many2one(
        "github.repository",
        string="Repository",
        required=True,
        ondelete="cascade",
    )
    integrator_id = fields.Many2one(
        "github.integrator",
        string="GitHub User",
        related="repository_id.integrator_id",
        store=True,
        readonly=True,
    )
    is_protected = fields.Boolean(string="Protected")
    is_default = fields.Boolean(string="Default Branch")
    last_commit_sha = fields.Char(string="Last Commit SHA")
    last_commit_author = fields.Char(string="Last Commit Author")
    last_commit_date = fields.Datetime(string="Last Commit Date")
    total_commits = fields.Integer(string="Total Commits")

    _sql_constraints = [
        (
            "unique_branch_per_repository",
            "unique(repository_id, name)",
            "Each branch name must be unique per repository.",
        )
    ]
