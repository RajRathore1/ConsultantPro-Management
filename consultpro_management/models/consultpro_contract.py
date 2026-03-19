# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from dateutil.relativedelta import relativedelta


class ConsultProContract(models.Model):
    _name = 'consultpro.contract'
    _description = 'ConsultPro Contract'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'
    _order = 'date_start desc'

    # ─────────────────────────────────────────────
    # Basic Info
    # ─────────────────────────────────────────────
    name = fields.Char(
        string='Contract Reference',
        required=True,
        readonly=True,
        copy=False,
        default='New',
        tracking=True,
    )
    title = fields.Char(string='Contract Title', required=True, tracking=True)
    client_id = fields.Many2one(
        'consultpro.client',
        string='Client',
        required=True,
        tracking=True,
        ondelete='restrict',
        index=True,
    )
    partner_id = fields.Many2one(
        related='client_id.partner_id',
        string='Partner',
        store=True,
    )
    contract_type = fields.Selection([
        ('fixed_price', 'Fixed Price'),
        ('time_material', 'Time & Material'),
        ('retainer', 'Retainer'),
        ('milestone', 'Milestone Based'),
    ], string='Contract Type', required=True, default='time_material', tracking=True)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('sent', 'Sent to Client'),
        ('approved', 'Approved'),
        ('active', 'Active'),
        ('expired', 'Expired'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True, required=True)

    # ─────────────────────────────────────────────
    # Dates & Financials
    # ─────────────────────────────────────────────
    date_start = fields.Date(string='Start Date', required=True, tracking=True)
    date_end = fields.Date(string='End Date', required=True, tracking=True)
    signed_date = fields.Date(string='Signed Date', tracking=True)
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id,
        required=True,
    )
    contract_value = fields.Monetary(
        string='Contract Value',
        currency_field='currency_id',
        tracking=True,
    )
    billing_cycle = fields.Selection([
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('milestone', 'On Milestone'),
        ('completion', 'On Completion'),
    ], string='Billing Cycle', default='monthly', tracking=True)
    payment_terms_id = fields.Many2one(
        'account.payment.term',
        string='Payment Terms',
    )

    # ─────────────────────────────────────────────
    # Services
    # ─────────────────────────────────────────────
    service_ids = fields.Many2many(
        'consultpro.service',
        'contract_service_rel',
        'contract_id', 'service_id',
        string='Services Included',
    )
    service_line_ids = fields.One2many(
        'consultpro.service.line',
        'contract_id',
        string='Service Lines',
    )

    # ─────────────────────────────────────────────
    # Team
    # ─────────────────────────────────────────────
    responsible_id = fields.Many2one(
        'res.users',
        string='Contract Manager',
        default=lambda self: self.env.user,
        tracking=True,
    )
    consultant_ids = fields.Many2many(
        'consultpro.consultant',
        'contract_consultant_rel',
        'contract_id', 'consultant_id',
        string='Assigned Consultants',
    )

    # ─────────────────────────────────────────────
    # Documents & Notes
    # ─────────────────────────────────────────────
    document_url = fields.Char(string='Contract Document URL')
    terms_conditions = fields.Html(string='Terms & Conditions')
    internal_notes = fields.Html(string='Internal Notes')

    # ─────────────────────────────────────────────
    # Computed
    # ─────────────────────────────────────────────
    project_ids = fields.One2many(
        'consultpro.project', 'contract_id', string='Projects'
    )
    project_count = fields.Integer(
        compute='_compute_project_count', store=True
    )
    invoiced_amount = fields.Monetary(
        string='Invoiced Amount',
        compute='_compute_invoiced_amount',
        currency_field='currency_id',
        store=True,
    )
    remaining_value = fields.Monetary(
        string='Remaining Value',
        compute='_compute_remaining_value',
        currency_field='currency_id',
    )
    days_remaining = fields.Integer(
        string='Days Remaining',
        compute='_compute_days_remaining',
    )
    progress = fields.Float(
        string='Progress (%)',
        compute='_compute_progress',
    )
    is_overdue = fields.Boolean(
        string='Overdue',
        compute='_compute_is_overdue',
        store=True,
    )

    # ─────────────────────────────────────────────
    # Compute Methods
    # ─────────────────────────────────────────────
    @api.depends('project_ids')
    def _compute_project_count(self):
        for rec in self:
            rec.project_count = len(rec.project_ids)

    @api.depends('project_ids.invoice_ids.amount_total', 'project_ids.invoice_ids.state')
    def _compute_invoiced_amount(self):
        for rec in self:
            total = 0.0
            for project in rec.project_ids:
                posted = project.invoice_ids.filtered(lambda i: i.state == 'posted')
                total += sum(posted.mapped('amount_total'))
            rec.invoiced_amount = total

    @api.depends('contract_value', 'invoiced_amount')
    def _compute_remaining_value(self):
        for rec in self:
            rec.remaining_value = rec.contract_value - rec.invoiced_amount

    @api.depends('date_end')
    def _compute_days_remaining(self):
        today = fields.Date.today()
        for rec in self:
            if rec.date_end:
                delta = rec.date_end - today
                rec.days_remaining = delta.days
            else:
                rec.days_remaining = 0

    @api.depends('date_start', 'date_end')
    def _compute_progress(self):
        today = fields.Date.today()
        for rec in self:
            if rec.date_start and rec.date_end:
                total_days = (rec.date_end - rec.date_start).days
                elapsed_days = (today - rec.date_start).days
                if total_days > 0:
                    rec.progress = min(100.0, max(0.0, (elapsed_days / total_days) * 100))
                else:
                    rec.progress = 0.0
            else:
                rec.progress = 0.0

    @api.depends('date_end', 'state')
    def _compute_is_overdue(self):
        today = fields.Date.today()
        for rec in self:
            rec.is_overdue = (
                rec.state == 'active'
                and rec.date_end
                and rec.date_end < today
            )

    # ─────────────────────────────────────────────
    # Constraints
    # ─────────────────────────────────────────────
    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        for rec in self:
            if rec.date_start and rec.date_end and rec.date_start > rec.date_end:
                raise ValidationError(_("End date must be after start date."))

    # ─────────────────────────────────────────────
    # ORM Overrides
    # ─────────────────────────────────────────────
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'consultpro.contract'
                ) or 'CNT-0001'
        return super().create(vals_list)

    # ─────────────────────────────────────────────
    # State Actions
    # ─────────────────────────────────────────────
    def action_send_to_client(self):
        self.ensure_one()
        template = self.env.ref(
            'consultpro_management.mail_template_contract_sent', raise_if_not_found=False
        )
        if template:
            template.send_mail(self.id, force_send=True)
        self.write({'state': 'sent'})

    def action_approve(self):
        self.write({'state': 'approved'})

    def action_activate(self):
        for rec in self:
            if not rec.date_start:
                raise UserError(_("Please set a start date before activating."))
        self.write({'state': 'active'})

    def action_cancel(self):
        for rec in self:
            if rec.state == 'active' and rec.project_ids.filtered(
                lambda p: p.state not in ('done', 'cancelled')
            ):
                raise UserError(_(
                    "Cannot cancel contract '%s': it has active projects."
                ) % rec.name)
        self.write({'state': 'cancelled'})

    def action_renew(self):
        self.ensure_one()
        new_contract = self.copy({
            'name': 'New',
            'state': 'draft',
            'date_start': self.date_end + relativedelta(days=1),
            'date_end': self.date_end + relativedelta(years=1),
            'signed_date': False,
        })
        return {
            'type': 'ir.actions.act_window',
            'name': _('Renewed Contract'),
            'res_model': 'consultpro.contract',
            'res_id': new_contract.id,
            'view_mode': 'form',
        }

    def action_view_projects(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Projects'),
            'res_model': 'consultpro.project',
            'view_mode': 'list,kanban,form',
            'domain': [('contract_id', '=', self.id)],
            'context': {'default_contract_id': self.id, 'default_client_id': self.client_id.id},
        }

    # ─────────────────────────────────────────────
    # Cron: Auto-expire contracts
    # ─────────────────────────────────────────────
    @api.model
    def cron_auto_expire_contracts(self):
        today = fields.Date.today()
        expired = self.search([
            ('state', '=', 'active'),
            ('date_end', '<', today),
        ])
        expired.write({'state': 'expired'})
        for contract in expired:
            contract.message_post(
                body=_("Contract automatically expired on %s.") % str(today),
                subject=_("Contract Expired"),
            )