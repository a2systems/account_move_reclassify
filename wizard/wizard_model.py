from odoo import fields,models, api, _
from odoo.exceptions import UserError, ValidationError
import logging
from datetime import date

_logger = logging.getLogger(__name__)

class AccountMoveReclassifyWizard(models.TransientModel):
    _name = 'account.move.reclassify.wizard'
    _description = 'account.move.reclassify.wizard'

    source_account_id = fields.Many2one('account.account',string='Cuenta a reclasificar')
    dest_account_id = fields.Many2one('account.account',string='Cuenta reclasificada')
    percent = fields.Integer('Porcentaje',default=100)

    def btn_confirm(self):
        if self.percent < 0 or self.percent > 100:
            raise ValidationError('Porcentaje incorrecto')
        percent = self.percent / 100
        if not self.source_account_id or not self.dest_account_id:
            raise ValidationError('Por favor ingrese lacuentas')
        if self.env.context.get('active_model') == 'account.move':
            active_ids = self.env.context.get('active_ids')
            for active_id in active_ids:
                move = self.env['account.move'].browse(active_id)
                move_lines = move.line_ids.filtered(lambda l: l.account_id.id == self.source_account_id.id)
                if move.move_type == 'entry' and move_lines and not move.reclassify_id:
                    vals_move = {
                            'move_type': 'entry',
                            'ref': move.ref,
                            'date': move.date,
                            'journal_id': move.journal_id.id,
                            'auto_post': move.auto_post,
                            'to_check': move.to_check,
                            'fiscal_position_id': move.fiscal_position_id and move.fiscal_position_id.id or None,
                            'company_id': move.company_id.id,
                            }
                    move_id = self.env['account.move'].create(vals_move)
                    for move_line in move_lines:
                        if move_line.debit > 0:
                            vals_debit = {
                                    'move_id': move_id.id,
                                    'account_id': self.dest_account_id.id,
                                    'name': 'Reversal %s'%(self.source_account_id.name),
                                    'credit': 0,
                                    'debit': move_line.debit * percent,
                                    'date': move_line.date,
                                    'partner_id': move_line.partner_id and move_line.partner_id.id or None,
                                    'amount_currency': abs(move_line.amount_currency) * percent,
                                    'currency_id': move_line.currency_id and move_line.currency_id.id or None,
                                    }
                            debit_id = self.env['account.move.line'].with_context(check_move_validity=False).create(vals_debit)
                            vals_credit = {
                                    'move_id': move_id.id,
                                    'account_id': self.source_account_id.id,
                                    'name': 'Reversal %s'%(self.source_account_id.name),
                                    'credit': move_line.debit * percent,
                                    'debit': 0,
                                    'date': move_line.date,
                                    'partner_id': move_line.partner_id and move_line.partner_id.id or None,
                                    'amount_currency': abs(move_line.amount_currency) * (-1) * percent,
                                    'currency_id': move_line.currency_id and move_line.currency_id.id or None,
                                    }
                            credit_id = self.env['account.move.line'].with_context(check_move_validity=False).create(vals_credit)
                        if move_line.credit > 0:
                            vals_credit = {
                                    'move_id': move_id.id,
                                    'account_id': self.dest_account_id.id,
                                    'name': 'Reversal %s'%(self.source_account_id.name),
                                    'debit': 0,
                                    'credit': move_line.credit * percent,
                                    'date': move_line.date,
                                    'partner_id': move_line.partner_id and move_line.partner_id.id or None,
                                    'amount_currency': abs(move_line.amount_currency) * (-1) * percent,
                                    'currency_id': move_line.currency_id and move_line.currency_id.id or None,
                                    }
                            credit_id = self.env['account.move.line'].with_context(check_move_validity=False).create(vals_credit)
                            vals_debit = {
                                    'move_id': move_id.id,
                                    'account_id': self.source_account_id.id,
                                    'name': 'Reversal %s'%(self.source_account_id.name),
                                    'debit': move_line.credit * percent,
                                    'credit': 0,
                                    'date': move_line.date,
                                    'partner_id': move_line.partner_id and move_line.partner_id.id or None,
                                    'amount_currency': abs(move_line.amount_currency) * percent,
                                    'currency_id': move_line.currency_id and move_line.currency_id.id or None,
                                    }
                            debit_id = self.env['account.move.line'].with_context(check_move_validity=False).create(vals_debit)
                    move.reclassify_id = move_id.id
