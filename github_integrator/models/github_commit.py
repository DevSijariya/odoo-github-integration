from odoo import fields, models


class GitHubCommit(models.Model):
    _name = "github.commit"
    _description = "GitHub Commit"
    _order = "commit_date desc, id desc"

    sha = fields.Char(string="SHA", required=True)
    short_sha = fields.Char(string="Short SHA")
    message = fields.Char(string="Message")
    author_name = fields.Char(string="Author Name")
    author_login = fields.Char(string="Author Login")
    commit_date = fields.Datetime(string="Commit Date")
    commit_url = fields.Char(string="Commit URL")
    branch_name = fields.Char(string="Branch")
    repository_id = fields.Many2one(
        "github.repository",
        string="Repository",
        required=True,
        ondelete="cascade",
    )

    _sql_constraints = [
        (
            "unique_commit_per_repository",
            "unique(repository_id, sha)",
            "Commit already exists for this repository.",
        )
    ]
