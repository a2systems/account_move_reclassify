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
    sum_debits = fields.Float('Debitos')
    sum_credits = fields.Float('Creditos')

    @api.model
    def default_get(self, fields):
        context = self.env.context
        res = super(AccountMoveReclassifyWizard, self).default_get(fields)
        if context.get('active_model') == 'account.move.line':
            aml_ids = self.env['account.move.line'].browse(context.get('active_ids'))
            accounts = []
            currencies = []
            companies = []
            sum_debits = 0
            sum_credits = 0
            for aml_id in aml_ids:
                if aml_id.account_id.id not in accounts:
                    accounts.append(aml_id.account_id.id)
                if aml_id.currency_id.id not in currencies:
                    currencies.append(aml_id.currency_id.id)
                if aml_id.company_id.id not in companies:
                    companies.append(aml_id.company_id.id)
                sum_debits = sum_debits + aml_id.debit
                sum_credits = sum_credits + aml_id.credit
            if len(accounts) != 1:
                raise ValidationError('Debe seleccionar apuntes para solo una cuenta')
            if len(currencies) != 1:
                raise ValidationError('Debe seleccionar apuntes para solo una moneda')
            if len(companies) != 1:
                raise ValidationError('Debe seleccionar apuntes para solo una compania')
            res['source_account_id'] = accounts[0]
            res['sum_debits'] = sum_debits
            res['sum_credits'] = sum_credits
        return res


    def btn_confirm(self):
        if self.percent < 0 or self.percent > 100:
            raise ValidationError('Porcentaje incorrecto')
        percent = self.percent / 100
        if not self.source_account_id or not self.dest_account_id:
            raise ValidationError('Por favor ingrese lacuentas')
        if self.env.context.get('active_model') == 'account.move.line':
            journal_id = self.env['account.journal'].search([('type','=','general')],limit=1)
            if not journal_id:
                raise ValidationError('Por favor cree un diario del tipo Miscelaneos')
            vals_move = {
                'move_type': 'entry',
                'ref': 'Reclasificacion %s'%(self.source_account_id.display_name),
                'date': str(date.today()),
                'journal_id': journal_id.id,
                'to_check': True,
            }
            move_id = self.env['account.move'].create(vals_move)
            if self.sum_debits > self.sum_credits:
                debit = self.sum_debits - self.sum_credits
                credit = 0
            else:
                credit = self.sum_credits - self.sum_debits
                debit = 0
            #for move_line in move_lines:
            vals_source = {
                    'move_id': move_id.id,
                    'account_id': self.source_account_id.id,
                    'name': 'Reversal %s'%(self.source_account_id.name),
                    'debit': credit,
                    'credit': debit * percent,
                    'date': str(date.today()),
                }
            source_id = self.env['account.move.line'].with_context(check_move_validity=False).create(vals_source)
            vals_dest = {
                    'move_id': move_id.id,
                    'account_id': self.dest_account_id.id,
                    'name': 'Reversal %s'%(self.source_account_id.name),
                    'debit': debit * percent,
                    'credit': credit,
                    'date': str(date.today()),
                    }
            dest_id = self.env['account.move.line'].with_context(check_move_validity=False).create(vals_dest)
            active_ids = self.env.context.get('active_ids')
            for active_id in active_ids:
                move_line = self.env['account.move.line'].browse(active_id)
                move_line.reclassify_id = move_id.id
            #move_id.post()
            res = {
                'name': 'Asiento reclasificacion',
                'res_model': 'account.move',
                'view_mode': 'form',
                'res_id': move_id.id,
                'type': 'ir.actions.act_window',
                'target': 'new',
            }
            return res

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
                    move_id.action_post()
