from odoo import fields, models


class GitHubSyncLog(models.Model):
    _name = "github.sync.log"
    _description = "GitHub Sync Log"
    _order = "sync_time desc, id desc"

    repository_id = fields.Many2one(
        "github.repository",
        string="Repository",
        required=True,
        ondelete="cascade",
    )
    sync_time = fields.Datetime(string="Sync Time", default=fields.Datetime.now, required=True)
    status = fields.Selection(
        [("success", "Success"), ("failed", "Failed")],
        string="Status",
        required=True,
        default="success",
    )
    details = fields.Char(string="Details")
