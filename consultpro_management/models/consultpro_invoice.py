# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class AccountMove(models.Model):
    """Extend account.move to link invoices to ConsultPro projects."""
    _inherit = 'account.move'

    consultpro_project_id = fields.Many2one(
        'consultpro.project',
        string='ConsultPro Project',
        ondelete='set null',
        index=True,
    )
    consultpro_contract_id = fields.Many2one(
        'consultpro.contract',
        string='ConsultPro Contract',
        ondelete='set null',
        index=True,
    )
    consultpro_client_id = fields.Many2one(
        'consultpro.client',
        string='ConsultPro Client',
        compute='_compute_consultpro_client',
        store=True,
    )
    is_consultpro_invoice = fields.Boolean(
        string='ConsultPro Invoice',
        default=False,
    )
    timesheet_ids = fields.Many2many(
        'consultpro.timesheet',
        'invoice_timesheet_rel',
        'invoice_id', 'timesheet_id',
        string='Timesheets Covered',
        domain=[('state', '=', 'approved'), ('billable', '=', True)],
    )
    period_from = fields.Date(string='Billing Period From')
    period_to = fields.Date(string='Billing Period To')

    @api.depends('consultpro_project_id')
    def _compute_consultpro_client(self):
        for rec in self:
            rec.consultpro_client_id = rec.consultpro_project_id.client_id \
                if rec.consultpro_project_id else False

    def action_post(self):
        res = super().action_post()
        # Mark linked timesheets as invoiced
        for rec in self.filtered('is_consultpro_invoice'):
            rec.timesheet_ids.write({'state': 'invoiced', 'invoice_id': rec.id})
        return res

    def button_cancel(self):
        # Reset timesheets to approved if invoice is cancelled
        for rec in self.filtered('is_consultpro_invoice'):
            rec.timesheet_ids.filtered(
                lambda t: t.state == 'invoiced'
            ).write({'state': 'approved', 'invoice_id': False})
        return super().button_cancel()


class ConsultProInvoice(models.Model):
    """Standalone invoice record for audit trail (optional companion model)."""
    _name = 'consultpro.invoice'
    _description = 'ConsultPro Invoice Record'
    _inherit = ['mail.thread']
    _rec_name = 'name'
    _order = 'invoice_date desc'

    name = fields.Char(
        string='Invoice Reference',
        readonly=True,
        default='New',
        copy=False,
        tracking=True,
    )
    move_id = fields.Many2one(
        'account.move',
        string='Invoice',
        required=True,
        ondelete='cascade',
    )
    project_id = fields.Many2one(
        'consultpro.project',
        string='Project',
        required=True,
        ondelete='restrict',
        tracking=True,
    )
    client_id = fields.Many2one(
        related='project_id.client_id',
        string='Client',
        store=True,
    )
    contract_id = fields.Many2one(
        related='project_id.contract_id',
        string='Contract',
        store=True,
    )
    invoice_date = fields.Date(
        related='move_id.invoice_date',
        string='Invoice Date',
        store=True,
    )
    amount_total = fields.Monetary(
        related='move_id.amount_total',
        string='Total Amount',
        store=True,
        currency_field='currency_id',
    )
    currency_id = fields.Many2one(
        related='move_id.currency_id',
        string='Currency',
        store=True,
    )
    state = fields.Selection(
        related='move_id.state',
        string='Invoice State',
        store=True,
    )
    payment_state = fields.Selection(
        related='move_id.payment_state',
        string='Payment State',
        store=True,
    )
    period_from = fields.Date(string='Period From')
    period_to = fields.Date(string='Period To')
    timesheet_ids = fields.Many2many(
        'consultpro.timesheet',
        'consultpro_invoice_ts_rel',
        'consultpro_invoice_id', 'timesheet_id',
        string='Timesheets',
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'consultpro.invoice'
                ) or 'INV-0001'
        return super().create(vals_list)

    def action_open_invoice(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Invoice'),
            'res_model': 'account.move',
            'res_id': self.move_id.id,
            'view_mode': 'form',
        }