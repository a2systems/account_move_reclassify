from odoo import tools, models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import date,datetime


class AccountMove(models.Model):
    _inherit = "account.move"

    reclassify_id = fields.Many2one(
            comodel_name='account.move',
            string='Asiento Reclasificacion',
            copy=False
            )
