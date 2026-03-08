from odoo import models, fields
from odoo.exceptions import UserError

class GitHubRepository(models.Model):
    _name = 'github.repository'
    _description = 'GitHub Repository'

    name = fields.Char(string='Repository Name', required=True)
    full_name = fields.Char(string='Full Name')
    description = fields.Text(string='Description')
    primary_lanaguage = fields.Char(string='Primary Language')
    default_branch = fields.Char(string='Default Branch')
    stars = fields.Integer(string='Stars')
    forks = fields.Integer(string='Forks')
    open_issues = fields.Integer(string='Open Issues')
    total_commits = fields.Integer(string='Total Commits')
    total_branches = fields.Integer(string='Total Branches')
    total_pull_requests = fields.Integer(string='Total Pull Requests')
    total_contributors = fields.Integer(string='Total Contributors')
    repository_url = fields.Char(string='Repository URL')
    clone_url = fields.Char(string='Clone URL')
    ssh_url = fields.Char(string='SSH URL')
    repository_size_kb = fields.Integer(string='Repository Size (KB)')
    is_fork = fields.Boolean(string='Is Fork')
    is_private = fields.Boolean(string='Private Repository')
    last_updated = fields.Datetime(string='Last Updated')
    integrator_id = fields.Many2one('github.integrator', string='GitHub User')
    sync_status = fields.Selection([('synced', 'Synced'), ('failed', 'Failed')], string='Sync Status')
    linked_project_id = fields.Many2one('project.project', string='Linked Project', readonly=True)

    branch_ids = fields.One2many('github.branch', 'repository_id', string='Branches')
    commit_ids = fields.One2many('github.commit', 'repository_id', string='Commits')
    issue_ids = fields.One2many('github.issue', 'repository_id', string='Issues')
    collaborator_ids = fields.One2many('github.collaborator', 'repository_id', string='Collaborators')
    sync_log_ids = fields.One2many('github.sync.log', 'repository_id', string='Sync Info')

    def _compute_full_name(self):
        self.ensure_one()
        if self.full_name:
            return self.full_name
        if not self.repository_url:
            return False
        # https://github.com/org/repo -> org/repo
        return self.repository_url.rstrip("/").split("github.com/")[-1]

    def action_sync_repository(self):
        self.ensure_one()
        if not self.integrator_id:
            return False
        integrator = self.integrator_id
        headers = integrator._build_headers()
        full_name = self._compute_full_name()
        if not full_name:
            return False

        repo_response = integrator._github_request(
            f"{integrator.url}/repos/{full_name}",
            headers=headers,
        )
        repo = repo_response.json()
        payload = integrator._collect_repo_payload_static(
            repo,
            headers,
            {
                "url": integrator.url,
                "username": integrator.username,
                "sync_branches": integrator.sync_branches,
                "sync_commits": integrator.sync_commits,
                "sync_commit_details": integrator.sync_commit_details,
                "sync_issues": integrator.sync_issues,
                "sync_collaborators": integrator.sync_collaborators,
                "sync_timeout": integrator.sync_timeout,
                "commit_limit_per_branch": integrator.commit_limit_per_branch,
                "branch_limit_per_repository": integrator.branch_limit_per_repository,
            },
        )
        self.write(payload["repo_values"])
        integrator._sync_repo_children(self, payload)
        self.write({"sync_status": "synced"})
        return {
            "type": "ir.actions.client",
            "tag": "reload",
        }

    def action_open_in_github(self):
        self.ensure_one()
        if not self.repository_url:
            return False
        return {
            "type": "ir.actions.act_url",
            "url": self.repository_url,
            "target": "new",
        }

    def action_create_project(self):
        self.ensure_one()
        if self.linked_project_id:
            return {
                "type": "ir.actions.act_window",
                "name": "Project",
                "res_model": "project.project",
                "view_mode": "form",
                "res_id": self.linked_project_id.id,
                "target": "current",
            }

        if not self.name:
            raise UserError("Repository name is required to create a project.")

        project = self.env["project.project"].create({
            "name": self.full_name or self.name,
            "description": self.description or "",
            "github_repository_id": self.id,
        })
        self.write({"linked_project_id": project.id})
        return {
            "type": "ir.actions.act_window",
            "name": "Project",
            "res_model": "project.project",
            "view_mode": "form",
            "res_id": project.id,
            "target": "current",
        }

    def action_view_branches(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Branches",
            "view_mode": "list,form",
            "res_model": "github.branch",
            "domain": [("repository_id", "=", self.id)],
            "context": {"default_repository_id": self.id},
        }

    def action_view_issues(self):
        self.ensure_one()
        list_view = self.env.ref("github_integrator.github_issue_list_view", raise_if_not_found=False)
        form_view = self.env.ref("github_integrator.github_issue_form_view", raise_if_not_found=False)
        views = []
        if list_view:
            views.append((list_view.id, "list"))
        if form_view:
            views.append((form_view.id, "form"))
        return {
            "type": "ir.actions.act_window",
            "name": "Issues",
            "view_mode": "list,form",
            "res_model": "github.issue",
            "views": views or False,
            "domain": [("repository_id", "=", self.id)],
            "context": {"default_repository_id": self.id},
        }

    def action_view_commits(self):
        self.ensure_one()
        list_view = self.env.ref("github_integrator.github_commit_list_view")
        form_view = self.env.ref("github_integrator.github_commit_form_view")
        return {
            "type": "ir.actions.act_window",
            "name": "Commits",
            "view_mode": "list,form",
            "res_model": "github.commit",
            "views": [(list_view.id, "list"), (form_view.id, "form")],
            "domain": [("repository_id", "=", self.id)],
            "context": {"default_repository_id": self.id},
        }

    def action_view_collaborators(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Collaborators",
            "view_mode": "list,form",
            "res_model": "github.collaborator",
            "domain": [("repository_id", "=", self.id)],
            "context": {"default_repository_id": self.id},
        }
