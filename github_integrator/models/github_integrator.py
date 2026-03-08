import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from odoo import fields, models
from odoo.exceptions import UserError


class GitHubIntegrator(models.Model):
    _name = "github.integrator"
    _description = "GitHub Integrator"
    _rec_name = "username"

    url = fields.Char(string="GitHub API URL", required=True, default="https://api.github.com")
    access_token = fields.Char(string="Access Token", required=True)
    username = fields.Char(string="GitHub Username", required=True)
    repository = fields.Integer(string="Repository Count")
    active_repo = fields.Boolean(string="Active", default=True)
    sync_status = fields.Selection(
        [("idle", "Idle"), ("running", "Running"), ("success", "Success"), ("failed", "Failed")],
        string="Sync Status",
        default="idle",
    )
    last_sync_at = fields.Datetime(string="Last Sync At")

    auto_sync = fields.Boolean(string="Auto Sync", default=True)
    sync_repositories = fields.Boolean(string="Sync Repositories", default=True)
    sync_branches = fields.Boolean(string="Sync Branches", default=True)
    sync_commits = fields.Boolean(string="Sync Commits", default=True)
    sync_commit_details = fields.Boolean(string="Sync Commit Details", default=False)
    commit_limit_per_branch = fields.Integer(string="Commit Limit per Branch", default=15)
    sync_issues = fields.Boolean(string="Sync Issues", default=True)
    sync_collaborators = fields.Boolean(string="Sync Collaborators", default=False)

    enable_multithreading = fields.Boolean(string="Enable Multi-threading Sync", default=True)
    max_worker_threads = fields.Integer(string="Max Worker Threads", default=4)
    thread_delay = fields.Float(string="Thread Delay (seconds)", default=0.20)
    sync_timeout = fields.Integer(string="Sync Timeout (seconds)", default=45)
    branch_limit_per_repository = fields.Integer(string="Branch Limit per Repository", default=0)

    def _build_headers(self):
        self.ensure_one()
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/vnd.github+json",
        }

    def _github_request(self, api_url, headers, params=None, fail_silently=False):
        self.ensure_one()
        response = requests.get(
            api_url,
            headers=headers,
            params=params or {},
            timeout=max(self.sync_timeout or 45, 5),
        )
        if response.status_code != 200:
            if fail_silently:
                return False
            raise UserError(f"GitHub API failed: {response.status_code} - {response.text}")
        return response

    @staticmethod
    def _github_request_static(api_url, headers, timeout_seconds, params=None, fail_silently=False):
        response = requests.get(
            api_url,
            headers=headers,
            params=params or {},
            timeout=max(timeout_seconds or 45, 5),
        )
        if response.status_code != 200:
            if fail_silently:
                return False
            raise UserError(f"GitHub API failed: {response.status_code} - {response.text}")
        return response

    def _github_get_paginated(self, api_url, headers, extra_params=None, fail_silently=False):
        self.ensure_one()
        all_records = []
        page = 1
        per_page = 100
        while True:
            params = {"per_page": per_page, "page": page}
            if extra_params:
                params.update(extra_params)
            response = self._github_request(
                api_url,
                headers=headers,
                params=params,
                fail_silently=fail_silently,
            )
            if not response:
                return []

            records = response.json()
            if not records:
                break

            all_records.extend(records)
            if len(records) < per_page:
                break
            page += 1
        return all_records

    @classmethod
    def _github_get_paginated_static(cls, api_url, headers, timeout_seconds, extra_params=None, fail_silently=False):
        all_records = []
        page = 1
        per_page = 100
        while True:
            params = {"per_page": per_page, "page": page}
            if extra_params:
                params.update(extra_params)
            response = cls._github_request_static(
                api_url,
                headers=headers,
                timeout_seconds=timeout_seconds,
                params=params,
                fail_silently=fail_silently,
            )
            if not response:
                return []
            records = response.json()
            if not records:
                break
            all_records.extend(records)
            if len(records) < per_page:
                break
            page += 1
        return all_records

    def _github_count_items(self, api_url, headers, params=None, fail_silently=False):
        self.ensure_one()
        query = {"per_page": 1, "page": 1}
        if params:
            query.update(params)
        response = self._github_request(
            api_url,
            headers=headers,
            params=query,
            fail_silently=fail_silently,
        )
        if not response:
            return 0

        records = response.json()
        if not records:
            return 0

        link = response.headers.get("Link", "")
        match = re.search(r"[?&]page=(\d+)>; rel=\"last\"", link)
        if match:
            return int(match.group(1))
        return len(records)

    @classmethod
    def _github_count_items_static(cls, api_url, headers, timeout_seconds, params=None, fail_silently=False):
        query = {"per_page": 1, "page": 1}
        if params:
            query.update(params)
        response = cls._github_request_static(
            api_url,
            headers=headers,
            timeout_seconds=timeout_seconds,
            params=query,
            fail_silently=fail_silently,
        )
        if not response:
            return 0
        records = response.json()
        if not records:
            return 0
        link = response.headers.get("Link", "")
        match = re.search(r"[?&]page=(\d+)>; rel=\"last\"", link)
        if match:
            return int(match.group(1))
        return len(records)

    @staticmethod
    def _fmt_datetime(value):
        if not value:
            return False
        return value.replace("T", " ").replace("Z", "")

    def _sync_repo_children(self, repository_record, payload):
        branches = payload.get("branches")
        commits = payload.get("commits")
        issues = payload.get("issues")
        collaborators = payload.get("collaborators")

        if branches is not None:
            existing_branches = self.env["github.branch"].search([
                ("repository_id", "=", repository_record.id)
            ])
            existing_by_name = {branch.name: branch for branch in existing_branches}
            synced_branch_names = set()

            for branch in branches:
                branch_name = branch.get("name")
                if not branch_name:
                    continue
                synced_branch_names.add(branch_name)

                vals = {
                    "name": branch_name,
                    "is_default": branch_name == payload.get("default_branch"),
                    "is_protected": branch.get("protected", False),
                    "last_commit_sha": branch.get("last_commit_sha"),
                    "last_commit_author": branch.get("last_commit_author"),
                    "last_commit_date": self._fmt_datetime(branch.get("last_commit_date")),
                    "total_commits": branch.get("total_commits", 0),
                    "repository_id": repository_record.id,
                }
                existing_branch = existing_by_name.get(branch_name)
                if existing_branch:
                    existing_branch.write(vals)
                else:
                    self.env["github.branch"].create(vals)

            stale_branches = existing_branches.filtered(lambda b: b.name not in synced_branch_names)
            if stale_branches:
                stale_branches.unlink()

        if commits is not None:
            existing_commits = self.env["github.commit"].search([
                ("repository_id", "=", repository_record.id)
            ])
            existing_by_sha = {commit.sha: commit for commit in existing_commits}
            for commit in commits:
                sha = commit.get("sha")
                if not sha:
                    continue
                vals = {
                    "sha": sha,
                    "short_sha": sha[:8],
                    "message": commit.get("message"),
                    "author_name": commit.get("author_name"),
                    "author_login": commit.get("author_login"),
                    "commit_date": self._fmt_datetime(commit.get("commit_date")),
                    "commit_url": commit.get("commit_url"),
                    "branch_name": commit.get("branch_name"),
                    "repository_id": repository_record.id,
                }
                existing_commit = existing_by_sha.get(sha)
                if existing_commit:
                    existing_commit.write(vals)
                else:
                    self.env["github.commit"].create(vals)

        if issues is not None:
            existing_issues = self.env["github.issue"].search([
                ("repository_id", "=", repository_record.id)
            ])
            existing_issue_by_id = {issue.github_issue_id: issue for issue in existing_issues}
            synced_issue_ids = set()
            for issue in issues:
                issue_id = issue.get("id")
                if not issue_id:
                    continue
                synced_issue_ids.add(issue_id)
                vals = {
                    "github_issue_id": issue_id,
                    "issue_number": issue.get("number"),
                    "title": issue.get("title"),
                    "state": issue.get("state"),
                    "author_login": (issue.get("user") or {}).get("login"),
                    "issue_url": issue.get("html_url"),
                    "created_at": self._fmt_datetime(issue.get("created_at")),
                    "updated_at": self._fmt_datetime(issue.get("updated_at")),
                    "repository_id": repository_record.id,
                }
                existing_issue = existing_issue_by_id.get(issue_id)
                if existing_issue:
                    existing_issue.write(vals)
                else:
                    self.env["github.issue"].create(vals)

            stale_issues = existing_issues.filtered(lambda i: i.github_issue_id not in synced_issue_ids)
            if stale_issues:
                stale_issues.unlink()

        if collaborators is not None:
            existing_collaborators = self.env["github.collaborator"].search([
                ("repository_id", "=", repository_record.id)
            ])
            existing_by_login = {collab.login: collab for collab in existing_collaborators}
            synced_logins = set()
            for collaborator in collaborators:
                login = collaborator.get("login")
                if not login:
                    continue
                synced_logins.add(login)
                permissions = collaborator.get("permissions") or {}
                vals = {
                    "login": login,
                    "name": collaborator.get("name"),
                    "profile_url": collaborator.get("html_url"),
                    "is_admin": permissions.get("admin", False),
                    "can_push": permissions.get("push", False),
                    "can_pull": permissions.get("pull", False),
                    "repository_id": repository_record.id,
                }
                existing_collaborator = existing_by_login.get(login)
                if existing_collaborator:
                    existing_collaborator.write(vals)
                else:
                    self.env["github.collaborator"].create(vals)

            stale_collaborators = existing_collaborators.filtered(lambda c: c.login not in synced_logins)
            if stale_collaborators:
                stale_collaborators.unlink()

        repository_record.write({
            "total_branches": payload.get("total_branches", repository_record.total_branches),
            "total_commits": payload.get("total_commits", repository_record.total_commits),
            "total_pull_requests": payload.get("total_pull_requests", repository_record.total_pull_requests),
            "total_contributors": payload.get("total_contributors", repository_record.total_contributors),
            "open_issues": payload.get("open_issues", repository_record.open_issues),
        })

    @classmethod
    def _collect_repo_payload_static(cls, repo, headers, config):
        full_name = repo.get("full_name")
        if not full_name:
            owner = (repo.get("owner") or {}).get("login") or config.get("username")
            full_name = f"{owner}/{repo.get('name')}"

        default_branch = repo.get("default_branch")
        payload = {
            "repo_url": repo.get("html_url"),
            "full_name": full_name,
            "default_branch": default_branch,
            "repo_values": {
                "name": repo.get("name"),
                "full_name": full_name,
                "description": repo.get("description"),
                "primary_lanaguage": repo.get("language"),
                "default_branch": default_branch,
                "stars": repo.get("stargazers_count"),
                "forks": repo.get("forks_count"),
                "repository_size_kb": repo.get("size"),
                "repository_url": repo.get("html_url"),
                "clone_url": repo.get("clone_url"),
                "ssh_url": repo.get("ssh_url"),
                "is_private": repo.get("private"),
                "is_fork": repo.get("fork"),
                "last_updated": cls._fmt_datetime(repo.get("updated_at")),
                "sync_status": "synced",
            },
            "branches": None,
            "commits": None,
            "issues": None,
            "collaborators": None,
            "total_branches": 0,
            "total_commits": 0,
            "total_pull_requests": 0,
            "total_contributors": 0,
            "open_issues": 0,
        }

        if config.get("sync_branches"):
            branches = cls._github_get_paginated_static(
                f"{config['url']}/repos/{full_name}/branches",
                headers=headers,
                timeout_seconds=config.get("sync_timeout"),
                fail_silently=True,
            )
            if config.get("branch_limit_per_repository") and config["branch_limit_per_repository"] > 0:
                branches = branches[: config["branch_limit_per_repository"]]

            branch_rows = []
            for branch in branches:
                branch_name = branch.get("name")
                commit_sha = (branch.get("commit") or {}).get("sha")
                branch_row = {
                    "name": branch_name,
                    "protected": branch.get("protected", False),
                    "last_commit_sha": commit_sha,
                    "last_commit_author": False,
                    "last_commit_date": False,
                    "total_commits": 0,
                }

                if config.get("sync_commits") and branch_name:
                    branch_row["total_commits"] = cls._github_count_items_static(
                        f"{config['url']}/repos/{full_name}/commits",
                        headers=headers,
                        timeout_seconds=config.get("sync_timeout"),
                        params={"sha": branch_name},
                        fail_silently=True,
                    )
                if config.get("sync_commit_details") and commit_sha:
                    commit_response = cls._github_request_static(
                        f"{config['url']}/repos/{full_name}/commits/{commit_sha}",
                        headers=headers,
                        timeout_seconds=config.get("sync_timeout"),
                        fail_silently=True,
                    )
                    if commit_response:
                        commit_data = commit_response.json()
                        author = ((commit_data.get("commit") or {}).get("author") or {})
                        branch_row["last_commit_author"] = author.get("name")
                        branch_row["last_commit_date"] = author.get("date")

                if branch_name == default_branch:
                    payload["total_commits"] = branch_row["total_commits"]
                branch_rows.append(branch_row)

            payload["branches"] = branch_rows
            payload["total_branches"] = len(branch_rows)

        if config.get("sync_commits"):
            commit_params = {"sha": default_branch}
            if config.get("commit_limit_per_branch") and config["commit_limit_per_branch"] > 0:
                commit_params["per_page"] = config["commit_limit_per_branch"]
            else:
                commit_params["per_page"] = 30

            commits_api = cls._github_get_paginated_static(
                f"{config['url']}/repos/{full_name}/commits",
                headers=headers,
                timeout_seconds=config.get("sync_timeout"),
                extra_params=commit_params,
                fail_silently=True,
            )
            commit_rows = []
            for commit in commits_api:
                commit_info = commit.get("commit") or {}
                author_info = commit_info.get("author") or {}
                commit_rows.append({
                    "sha": commit.get("sha"),
                    "message": commit_info.get("message"),
                    "author_name": author_info.get("name"),
                    "author_login": (commit.get("author") or {}).get("login"),
                    "commit_date": author_info.get("date"),
                    "commit_url": commit.get("html_url"),
                    "branch_name": default_branch,
                })
            payload["commits"] = commit_rows

        if config.get("sync_issues"):
            issues = cls._github_get_paginated_static(
                f"{config['url']}/repos/{full_name}/issues",
                headers=headers,
                timeout_seconds=config.get("sync_timeout"),
                extra_params={"state": "all"},
                fail_silently=True,
            )
            issues = [issue for issue in issues if not issue.get("pull_request")]
            payload["issues"] = issues
            payload["open_issues"] = len([issue for issue in issues if issue.get("state") == "open"])

        if config.get("sync_collaborators"):
            collaborators = cls._github_get_paginated_static(
                f"{config['url']}/repos/{full_name}/collaborators",
                headers=headers,
                timeout_seconds=config.get("sync_timeout"),
                fail_silently=True,
            )
            payload["collaborators"] = collaborators
            payload["total_contributors"] = len(collaborators)

        payload["total_pull_requests"] = cls._github_count_items_static(
            f"{config['url']}/repos/{full_name}/pulls",
            headers=headers,
            timeout_seconds=config.get("sync_timeout"),
            params={"state": "all"},
            fail_silently=True,
        )
        return payload

    def _sync_repository_payloads(self, rec, headers, repos):
        payloads = []
        config = {
            "url": rec.url,
            "username": rec.username,
            "sync_branches": rec.sync_branches,
            "sync_commits": rec.sync_commits,
            "sync_commit_details": rec.sync_commit_details,
            "commit_limit_per_branch": rec.commit_limit_per_branch,
            "sync_issues": rec.sync_issues,
            "sync_collaborators": rec.sync_collaborators,
            "sync_timeout": rec.sync_timeout,
            "branch_limit_per_repository": rec.branch_limit_per_repository,
        }
        if rec.enable_multithreading and rec.max_worker_threads and rec.max_worker_threads > 1:
            with ThreadPoolExecutor(max_workers=rec.max_worker_threads) as executor:
                futures = []
                for repo in repos:
                    futures.append(executor.submit(self._collect_repo_payload_static, repo, headers, config))
                    if rec.thread_delay and rec.thread_delay > 0:
                        time.sleep(rec.thread_delay)
                for future in as_completed(futures):
                    payloads.append(future.result())
        else:
            for repo in repos:
                payloads.append(self._collect_repo_payload_static(repo, headers, config))
                if rec.thread_delay and rec.thread_delay > 0:
                    time.sleep(rec.thread_delay)
        return payloads

    def test_github_connection(self):
        for rec in self:
            headers = rec._build_headers()
            user_response = rec._github_request(f"{rec.url}/user", headers=headers)
            if not user_response:
                raise UserError("GitHub connection failed.")

            repos = rec._github_get_paginated(f"{rec.url}/user/repos", headers=headers)
            rec.write({"sync_status": "running", "repository": len(repos)})

            try:
                if not rec.sync_repositories:
                    rec.write({
                        "sync_status": "success",
                        "last_sync_at": fields.Datetime.now(),
                    })
                    return {"type": "ir.actions.client", "tag": "reload"}

                payloads = rec._sync_repository_payloads(rec, headers, repos)
                for payload in payloads:
                    existing_repo = self.env["github.repository"].search([
                        ("repository_url", "=", payload.get("repo_url")),
                        ("integrator_id", "=", rec.id),
                    ], limit=1)
                    values = dict(payload["repo_values"], integrator_id=rec.id)
                    if existing_repo:
                        existing_repo.write(values)
                        repository_record = existing_repo
                    else:
                        repository_record = self.env["github.repository"].create(values)

                    rec._sync_repo_children(repository_record, payload)
                    self.env["github.sync.log"].create({
                        "repository_id": repository_record.id,
                        "status": "success",
                        "details": "Repository synced successfully.",
                    })

                rec.write({
                    "sync_status": "success",
                    "last_sync_at": fields.Datetime.now(),
                })
            except Exception as sync_error:
                rec.write({"sync_status": "failed"})
                raise UserError(f"Sync failed: {sync_error}")

            return {"type": "ir.actions.client", "tag": "reload"}

    def action_view_repositories(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Repositories",
            "view_mode": "list,form",
            "res_model": "github.repository",
            "domain": [("integrator_id", "=", self.id)],
        }

    def action_sync_all_data(self):
        return self.test_github_connection()

    def action_clear_cache(self):
        for rec in self:
            repos = self.env["github.repository"].search([("integrator_id", "=", rec.id)])
            logs = self.env["github.sync.log"].search([("repository_id", "in", repos.ids)])
            if logs:
                logs.unlink()
        return {"type": "ir.actions.client", "tag": "reload"}
