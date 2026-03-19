# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError


class ConsultProProject(models.Model):
    _name = 'consultpro.project'
    _description = 'ConsultPro Project'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'
    _order = 'date_start desc'

    # ─────────────────────────────────────────────
    # Core
    # ─────────────────────────────────────────────
    name = fields.Char(
        string='Project Name',
        required=True,
        tracking=True,
        index=True,
    )
    code = fields.Char(
        string='Project Code',
        readonly=True,
        copy=False,
        default='New',
        index=True,
    )
    client_id = fields.Many2one(
        'consultpro.client',
        string='Client',
        required=True,
        tracking=True,
        ondelete='restrict',
        index=True,
    )
    contract_id = fields.Many2one(
        'consultpro.contract',
        string='Contract',
        domain="[('client_id', '=', client_id), ('state', 'in', ['active', 'approved'])]",
        tracking=True,
        ondelete='restrict',
    )
    odoo_project_id = fields.Many2one(
        'project.project',
        string='Odoo Project',
        ondelete='set null',
    )

    state = fields.Selection([
        ('draft', 'Draft'),
        ('planning', 'Planning'),
        ('in_progress', 'In Progress'),
        ('on_hold', 'On Hold'),
        ('review', 'Under Review'),
        ('done', 'Completed'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True, required=True, index=True)

    priority = fields.Selection([
        ('0', 'Normal'),
        ('1', 'High'),
        ('2', 'Critical'),
    ], string='Priority', default='0')

    project_type = fields.Selection([
        ('implementation', 'Implementation'),
        ('consulting', 'Consulting'),
        ('audit', 'Audit'),
        ('training', 'Training'),
        ('support', 'Support'),
        ('research', 'Research'),
    ], string='Project Type', required=True, default='consulting')

    # ─────────────────────────────────────────────
    # Dates
    # ─────────────────────────────────────────────
    date_start = fields.Date(string='Start Date', required=True, tracking=True)
    date_end = fields.Date(string='End Date', required=True, tracking=True)
    actual_end_date = fields.Date(string='Actual End Date')

    # ─────────────────────────────────────────────
    # Budget & Financials
    # ─────────────────────────────────────────────
    currency_id = fields.Many2one(
        related='contract_id.currency_id',
        store=True,
        default=lambda self: self.env.company.currency_id,
    )
    budget = fields.Monetary(
        string='Budget',
        currency_field='currency_id',
        tracking=True,
    )
    estimated_hours = fields.Float(string='Estimated Hours')
    analytic_account_id = fields.Many2one(
        'account.analytic.account',
        string='Analytic Account',
    )

    # ─────────────────────────────────────────────
    # Team
    # ─────────────────────────────────────────────
    project_manager_id = fields.Many2one(
        'res.users',
        string='Project Manager',
        default=lambda self: self.env.user,
        tracking=True,
        required=True,
    )
    consultant_ids = fields.Many2many(
        'consultpro.consultant',
        'project_consultant_rel',
        'project_id', 'consultant_id',
        string='Consultants',
    )

    # ─────────────────────────────────────────────
    # Description
    # ─────────────────────────────────────────────
    description = fields.Html(string='Project Description')
    scope_of_work = fields.Html(string='Scope of Work')
    objectives = fields.Text(string='Objectives')
    risks = fields.Text(string='Risks & Mitigations')

    # ─────────────────────────────────────────────
    # Relations
    # ─────────────────────────────────────────────
    task_ids = fields.One2many(
        'consultpro.task', 'project_id', string='Tasks'
    )
    timesheet_ids = fields.One2many(
        'consultpro.timesheet', 'project_id', string='Timesheets'
    )
    invoice_ids = fields.One2many(
        'account.move', 'consultpro_project_id', string='Invoices'
    )

    # ─────────────────────────────────────────────
    # Computed KPIs
    # ─────────────────────────────────────────────
    task_count = fields.Integer(compute='_compute_task_count', store=True)
    task_done_count = fields.Integer(compute='_compute_task_count', store=True)
    completion_rate = fields.Float(compute='_compute_task_count', store=True, string='Completion %')
    logged_hours = fields.Float(compute='_compute_logged_hours', store=True, string='Logged Hours')
    remaining_hours = fields.Float(compute='_compute_remaining_hours', string='Remaining Hours')
    budget_spent = fields.Monetary(
        compute='_compute_budget_spent',
        currency_field='currency_id',
        store=True,
        string='Budget Spent',
    )
    budget_remaining = fields.Monetary(
        compute='_compute_budget_remaining',
        currency_field='currency_id',
        string='Budget Remaining',
    )
    is_over_budget = fields.Boolean(compute='_compute_budget_remaining', store=True)
    invoice_count = fields.Integer(compute='_compute_invoice_count')
    days_remaining = fields.Integer(compute='_compute_days_remaining')

    @api.depends('task_ids.state')
    def _compute_task_count(self):
        for rec in self:
            total = len(rec.task_ids)
            done = len(rec.task_ids.filtered(lambda t: t.state == 'done'))
            rec.task_count = total
            rec.task_done_count = done
            rec.completion_rate = (done / total * 100) if total else 0.0

    @api.depends('timesheet_ids.hours', 'timesheet_ids.state')
    def _compute_logged_hours(self):
        for rec in self:
            approved = rec.timesheet_ids.filtered(lambda t: t.state == 'approved')
            rec.logged_hours = sum(approved.mapped('hours'))

    @api.depends('estimated_hours', 'logged_hours')
    def _compute_remaining_hours(self):
        for rec in self:
            rec.remaining_hours = max(0.0, rec.estimated_hours - rec.logged_hours)

    @api.depends('timesheet_ids.hours', 'timesheet_ids.state', 'consultant_ids.cost_rate')
    def _compute_budget_spent(self):
        for rec in self:
            total_cost = 0.0
            approved = rec.timesheet_ids.filtered(lambda t: t.state == 'approved')
            for ts in approved:
                rate = ts.consultant_id.cost_rate if ts.consultant_id else 0.0
                total_cost += ts.hours * rate
            rec.budget_spent = total_cost

    @api.depends('budget', 'budget_spent')
    def _compute_budget_remaining(self):
        for rec in self:
            rec.budget_remaining = rec.budget - rec.budget_spent
            rec.is_over_budget = rec.budget_spent > rec.budget

    @api.depends('invoice_ids')
    def _compute_invoice_count(self):
        for rec in self:
            rec.invoice_count = len(rec.invoice_ids)

    @api.depends('date_end')
    def _compute_days_remaining(self):
        today = fields.Date.today()
        for rec in self:
            rec.days_remaining = (rec.date_end - today).days if rec.date_end else 0

    # ─────────────────────────────────────────────
    # ORM
    # ─────────────────────────────────────────────
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('code', 'New') == 'New':
                vals['code'] = self.env['ir.sequence'].next_by_code(
                    'consultpro.project'
                ) or 'PRJ-0001'
        records = super().create(vals_list)
        for rec in records:
            rec._create_odoo_project()
        return records

    def _create_odoo_project(self):
        """Optionally sync with native project.project"""
        if not self.odoo_project_id:
            odoo_proj = self.env['project.project'].create({
                'name': self.name,
                'partner_id': self.client_id.partner_id.id,
                'user_id': self.project_manager_id.id,
                'date_start': self.date_start,
                'date': self.date_end,
            })
            self.odoo_project_id = odoo_proj.id

    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        for rec in self:
            if rec.date_start and rec.date_end and rec.date_start > rec.date_end:
                raise ValidationError(_("End date must be after start date."))

    # ─────────────────────────────────────────────
    # State Transitions
    # ─────────────────────────────────────────────
    def action_start(self):
        for rec in self:
            if rec.state != 'planning':
                raise UserError(_("Only projects in 'Planning' can be started."))
        self.write({'state': 'in_progress'})

    def action_hold(self):
        self.write({'state': 'on_hold'})

    def action_review(self):
        self.write({'state': 'review'})

    def action_complete(self):
        for rec in self:
            open_tasks = rec.task_ids.filtered(
                lambda t: t.state not in ('done', 'cancelled')
            )
            if open_tasks:
                raise UserError(_(
                    "Project '%s' has %d open task(s). Close them before completing."
                ) % (rec.name, len(open_tasks)))
        self.write({'state': 'done', 'actual_end_date': fields.Date.today()})

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    def action_view_invoices(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Invoices'),
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('consultpro_project_id', '=', self.id)],
            'context': {'default_consultpro_project_id': self.id, 'default_move_type': 'out_invoice'},
        }

    def action_view_tasks(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Tasks'),
            'res_model': 'consultpro.task',
            'view_mode': 'kanban,list,form',
            'domain': [('project_id', '=', self.id)],
            'context': {'default_project_id': self.id},
        }