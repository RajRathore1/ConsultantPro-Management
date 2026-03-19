# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class ConsultProInvoiceWizard(models.TransientModel):
    _name = 'consultpro.invoice.wizard'
    _description = 'Generate Invoice Wizard'

    project_id = fields.Many2one(
        'consultpro.project',
        string='Project',
        required=True,
        domain=[('state', '=', 'in_progress')],
        default=lambda self: self._default_project(),
    )
    client_id = fields.Many2one(
        related='project_id.client_id',
        string='Client',
        readonly=True,
    )
    contract_id = fields.Many2one(
        related='project_id.contract_id',
        string='Contract',
        readonly=True,
    )
    date_from = fields.Date(string='Period From', required=True)
    date_to = fields.Date(string='Period To', required=True, default=fields.Date.today)
    group_by = fields.Selection([
        ('consultant', 'By Consultant'),
        ('task', 'By Task'),
        ('activity', 'By Activity Type'),
        ('single', 'Single Line'),
    ], string='Group Lines By', default='consultant', required=True)

    timesheet_line_ids = fields.One2many(
        'consultpro.invoice.wizard.line',
        'wizard_id',
        string='Timesheets to Invoice',
    )
    total_hours = fields.Float(
        string='Total Hours',
        compute='_compute_totals',
    )
    total_amount = fields.Monetary(
        string='Total Amount',
        compute='_compute_totals',
        currency_field='currency_id',
    )
    currency_id = fields.Many2one(
        related='project_id.currency_id',
        string='Currency',
    )

    def _default_project(self):
        ctx = self.env.context
        if ctx.get('active_model') == 'consultpro.project':
            return ctx.get('active_id')
        return False

    @api.onchange('project_id', 'date_from', 'date_to')
    def _onchange_load_timesheets(self):
        if not self.project_id:
            self.timesheet_line_ids = [(5, 0, 0)]
            return
        domain = [
            ('project_id', '=', self.project_id.id),
            ('state', '=', 'approved'),
            ('billable', '=', True),
            ('invoice_id', '=', False),
        ]
        if self.date_from:
            domain.append(('date', '>=', self.date_from))
        if self.date_to:
            domain.append(('date', '<=', self.date_to))

        timesheets = self.env['consultpro.timesheet'].search(domain)
        lines = []
        for ts in timesheets:
            lines.append((0, 0, {
                'timesheet_id': ts.id,
                'consultant_id': ts.consultant_id.id,
                'date': ts.date,
                'task_id': ts.task_id.id if ts.task_id else False,
                'description': ts.name,
                'hours': ts.hours,
                'billing_rate': ts.billing_rate,
                'amount': ts.amount,
                'include': True,
            }))
        self.timesheet_line_ids = [(5, 0, 0)] + lines

    @api.depends('timesheet_line_ids.hours', 'timesheet_line_ids.amount', 'timesheet_line_ids.include')
    def _compute_totals(self):
        for rec in self:
            selected = rec.timesheet_line_ids.filtered('include')
            rec.total_hours = sum(selected.mapped('hours'))
            rec.total_amount = sum(selected.mapped('amount'))

    def action_generate_invoice(self):
        self.ensure_one()
        selected_ts = self.timesheet_line_ids.filtered('include').mapped('timesheet_id')
        if not selected_ts:
            raise UserError(_("Please select at least one timesheet to invoice."))

        invoice = self.env['consultpro.billing.service'].generate_invoice_from_timesheets(
            project_id=self.project_id.id,
            timesheet_ids=selected_ts.ids,
            date_from=self.date_from,
            date_to=self.date_to,
            group_by=self.group_by,
        )

        return {
            'type': 'ir.actions.act_window',
            'name': _('Generated Invoice'),
            'res_model': 'account.move',
            'res_id': invoice.id,
            'view_mode': 'form',
            'target': 'current',
        }


class ConsultProInvoiceWizardLine(models.TransientModel):
    _name = 'consultpro.invoice.wizard.line'
    _description = 'Invoice Wizard Timesheet Line'
    _order = 'date'

    wizard_id = fields.Many2one(
        'consultpro.invoice.wizard',
        ondelete='cascade',
    )
    timesheet_id = fields.Many2one('consultpro.timesheet', string='Timesheet', readonly=True)
    consultant_id = fields.Many2one('consultpro.consultant', string='Consultant', readonly=True)
    date = fields.Date(string='Date', readonly=True)
    task_id = fields.Many2one('consultpro.task', string='Task', readonly=True)
    description = fields.Char(string='Description', readonly=True)
    hours = fields.Float(string='Hours', readonly=True)
    billing_rate = fields.Float(string='Rate', readonly=True)
    currency_id = fields.Many2one(related='wizard_id.currency_id')
    amount = fields.Monetary(string='Amount', readonly=True, currency_field='currency_id')
    include = fields.Boolean(string='Include', default=True)