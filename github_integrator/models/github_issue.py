from odoo import fields, models
from odoo.exceptions import UserError


class GitHubIssue(models.Model):
    _name = "github.issue"
    _description = "GitHub Issue"

    github_issue_id = fields.Integer(string="Issue ID", required=True)
    issue_number = fields.Integer(string="Issue #")
    title = fields.Char(string="Title", required=True)
    state = fields.Selection(
        [("open", "Open"), ("closed", "Closed")],
        string="State",
    )
    author_login = fields.Char(string="Author")
    issue_url = fields.Char(string="Issue URL")
    created_at = fields.Datetime(string="Created At")
    updated_at = fields.Datetime(string="Updated At")
    linked_task_id = fields.Many2one("project.task", string="Linked Task", readonly=True)
    repository_id = fields.Many2one(
        "github.repository",
        string="Repository",
        required=True,
        ondelete="cascade",
    )

    _sql_constraints = [
        (
            "unique_issue_per_repository",
            "unique(repository_id, github_issue_id)",
            "Issue already exists for this repository.",
        )
    ]

    def action_open_in_github(self):
        self.ensure_one()
        if not self.issue_url:
            return False
        return {
            "type": "ir.actions.act_url",
            "url": self.issue_url,
            "target": "new",
        }

    def action_create_task(self):
        self.ensure_one()
        repository = self.repository_id
        if not repository.linked_project_id:
            raise UserError("Create or link a project in the repository before creating tasks.")

        if self.linked_task_id:
            return {
                "type": "ir.actions.act_window",
                "name": "Task",
                "res_model": "project.task",
                "view_mode": "form",
                "res_id": self.linked_task_id.id,
                "target": "current",
            }

        task = self.env["project.task"].create({
            "name": f"[#{self.issue_number}] {self.title}" if self.issue_number else self.title,
            "project_id": repository.linked_project_id.id,
            "description": f"GitHub Issue: {self.issue_url or ''}",
            "github_issue_id": self.id,
        })
        self.write({"linked_task_id": task.id})

        return {
            "type": "ir.actions.act_window",
            "name": "Task",
            "res_model": "project.task",
            "view_mode": "form",
            "res_id": task.id,
            "target": "current",
        }
