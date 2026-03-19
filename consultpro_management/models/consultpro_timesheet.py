# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError


class ConsultProTimesheet(models.Model):
    _name = 'consultpro.timesheet'
    _description = 'ConsultPro Timesheet Entry'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'
    _order = 'date desc, id desc'

    # ─────────────────────────────────────────────
    # Core
    # ─────────────────────────────────────────────
    name = fields.Char(
        string='Description',
        required=True,
        tracking=True,
    )
    date = fields.Date(
        string='Date',
        required=True,
        default=fields.Date.today,
        tracking=True,
        index=True,
    )
    consultant_id = fields.Many2one(
        'consultpro.consultant',
        string='Consultant',
        required=True,
        tracking=True,
        index=True,
        ondelete='restrict',
    )
    project_id = fields.Many2one(
        'consultpro.project',
        string='Project',
        required=True,
        tracking=True,
        index=True,
        ondelete='cascade',
    )
    task_id = fields.Many2one(
        'consultpro.task',
        string='Task',
        domain="[('project_id', '=', project_id)]",
        ondelete='set null',
        index=True,
    )
    client_id = fields.Many2one(
        related='project_id.client_id',
        string='Client',
        store=True,
    )

    # ─────────────────────────────────────────────
    # Hours
    # ─────────────────────────────────────────────
    hours = fields.Float(
        string='Hours',
        required=True,
        tracking=True,
        digits=(16, 2),
    )
    billable = fields.Boolean(
        string='Billable',
        default=True,
        tracking=True,
    )
    activity_type = fields.Selection([
        ('development', 'Development'),
        ('analysis', 'Analysis'),
        ('meeting', 'Meeting'),
        ('documentation', 'Documentation'),
        ('review', 'Review'),
        ('training', 'Training'),
        ('travel', 'Travel'),
        ('other', 'Other'),
    ], string='Activity Type', default='other', required=True)

    # ─────────────────────────────────────────────
    # State & Approval
    # ─────────────────────────────────────────────
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('invoiced', 'Invoiced'),
    ], string='Status', default='draft', tracking=True, required=True, index=True)

    approved_by_id = fields.Many2one(
        'res.users',
        string='Approved By',
        readonly=True,
        tracking=True,
    )
    approved_date = fields.Datetime(string='Approved Date', readonly=True)
    rejection_reason = fields.Text(string='Rejection Reason', tracking=True)

    # ─────────────────────────────────────────────
    # Financials
    # ─────────────────────────────────────────────
    currency_id = fields.Many2one(
        related='project_id.currency_id',
        string='Currency',
        store=True,
    )
    billing_rate = fields.Float(
        string='Billing Rate',
        compute='_compute_billing_rate',
        store=True,
        digits=(16, 2),
    )
    amount = fields.Monetary(
        string='Amount',
        compute='_compute_amount',
        currency_field='currency_id',
        store=True,
    )
    invoice_id = fields.Many2one(
        'account.move',
        string='Invoice',
        readonly=True,
    )

    # ─────────────────────────────────────────────
    # Analytic
    # ─────────────────────────────────────────────
    analytic_account_id = fields.Many2one(
        related='project_id.analytic_account_id',
        string='Analytic Account',
        store=True,
    )
    # Sync to hr.analytic.line
    hr_timesheet_id = fields.Many2one(
        'account.analytic.line',
        string='HR Timesheet Line',
        readonly=True,
    )

    # ─────────────────────────────────────────────
    # Computes
    # ─────────────────────────────────────────────
    @api.depends('consultant_id', 'billable')
    def _compute_billing_rate(self):
        for rec in self:
            if rec.billable and rec.consultant_id:
                rec.billing_rate = rec.consultant_id.billing_rate
            else:
                rec.billing_rate = 0.0

    @api.depends('hours', 'billing_rate', 'billable')
    def _compute_amount(self):
        for rec in self:
            rec.amount = rec.hours * rec.billing_rate if rec.billable else 0.0

    # ─────────────────────────────────────────────
    # Constraints
    # ─────────────────────────────────────────────
    @api.constrains('hours')
    def _check_hours(self):
        for rec in self:
            if rec.hours <= 0:
                raise ValidationError(_("Hours must be greater than zero."))
            if rec.hours > 24:
                raise ValidationError(_("Cannot log more than 24 hours in a single entry."))

    @api.constrains('date')
    def _check_date_not_future(self):
        today = fields.Date.today()
        for rec in self:
            if rec.date > today:
                raise ValidationError(_("Cannot log time for a future date."))

    # ─────────────────────────────────────────────
    # State Actions
    # ─────────────────────────────────────────────
    def action_submit(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_("Only draft timesheets can be submitted."))
        self.write({'state': 'submitted'})

    def action_approve(self):
        for rec in self:
            if rec.state != 'submitted':
                raise UserError(_("Only submitted timesheets can be approved."))
        self.write({
            'state': 'approved',
            'approved_by_id': self.env.user.id,
            'approved_date': fields.Datetime.now(),
        })
        self._sync_to_analytic()

    def action_reject(self, reason=None):
        self.write({
            'state': 'rejected',
            'rejection_reason': reason or _('Rejected by manager'),
        })

    def action_reset_draft(self):
        for rec in self:
            if rec.state == 'invoiced':
                raise UserError(_("Cannot reset an invoiced timesheet."))
        self.write({'state': 'draft', 'approved_by_id': False, 'approved_date': False})

    def _sync_to_analytic(self):
        """Create or update analytic line when timesheet is approved."""
        AnalyticLine = self.env['account.analytic.line']
        for rec in self:
            if rec.analytic_account_id and not rec.hr_timesheet_id:
                line = AnalyticLine.create({
                    'name': rec.name,
                    'date': rec.date,
                    'account_id': rec.analytic_account_id.id,
                    'unit_amount': rec.hours,
                    'amount': -rec.amount,  # cost side
                    'employee_id': rec.consultant_id.employee_id.id,
                })
                rec.hr_timesheet_id = line.id

    # ─────────────────────────────────────────────
    # Cron: Auto-remind un-submitted
    # ─────────────────────────────────────────────
    @api.model
    def cron_remind_unsubmitted(self):
        """Send reminders for draft timesheets older than 3 days."""
        from datetime import timedelta
        cutoff = fields.Date.today() - timedelta(days=3)
        old_drafts = self.search([
            ('state', '=', 'draft'),
            ('date', '<=', str(cutoff)),
        ])
        template = self.env.ref(
            'consultpro_management.mail_template_timesheet_reminder',
            raise_if_not_found=False,
        )
        if template:
            for ts in old_drafts:
                template.send_mail(ts.id)