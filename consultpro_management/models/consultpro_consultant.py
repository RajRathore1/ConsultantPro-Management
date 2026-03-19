# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ConsultProConsultant(models.Model):
    _name = 'consultpro.consultant'
    _description = 'ConsultPro Consultant'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'
    _order = 'name'

    # ─────────────────────────────────────────────
    # Identity
    # ─────────────────────────────────────────────
    name = fields.Char(
        string='Consultant Name',
        compute='_compute_name',
        store=True,
    )
    employee_id = fields.Many2one(
        'hr.employee',
        string='Employee',
        required=True,
        ondelete='restrict',
        tracking=True,
        index=True,
    )
    user_id = fields.Many2one(
        related='employee_id.user_id',
        string='Related User',
        store=True,
    )
    partner_id = fields.Many2one(
        related='employee_id.work_contact_id',
        string='Partner',
        store=True,
    )
    code = fields.Char(
        string='Consultant Code',
        readonly=True,
        copy=False,
        default='New',
    )
    active = fields.Boolean(default=True)

    # ─────────────────────────────────────────────
    # Professional Info
    # ─────────────────────────────────────────────
    designation = fields.Char(string='Designation', tracking=True)
    seniority = fields.Selection([
        ('junior', 'Junior Consultant'),
        ('mid', 'Consultant'),
        ('senior', 'Senior Consultant'),
        ('principal', 'Principal Consultant'),
        ('director', 'Director'),
        ('partner', 'Partner'),
    ], string='Seniority Level', default='mid', required=True, tracking=True)

    specialization_ids = fields.Many2many(
        'consultpro.service',
        'consultant_specialization_rel',
        'consultant_id', 'service_id',
        string='Specializations',
    )
    skill_ids = fields.Many2many(
        'hr.skill',
        'consultant_skill_rel',
        'consultant_id', 'skill_id',
        string='Skills',
    )
    years_of_experience = fields.Integer(string='Years of Experience')
    bio = fields.Html(string='Professional Bio')

    # ─────────────────────────────────────────────
    # Rates
    # ─────────────────────────────────────────────
    currency_id = fields.Many2one(
        'res.currency',
        default=lambda self: self.env.company.currency_id,
    )
    cost_rate = fields.Monetary(
        string='Internal Cost Rate (hourly)',
        currency_field='currency_id',
        tracking=True,
    )
    billing_rate = fields.Monetary(
        string='Billing Rate (hourly)',
        currency_field='currency_id',
        tracking=True,
    )

    # ─────────────────────────────────────────────
    # Availability
    # ─────────────────────────────────────────────
    availability = fields.Selection([
        ('available', 'Available'),
        ('partially', 'Partially Available'),
        ('booked', 'Fully Booked'),
        ('leave', 'On Leave'),
    ], string='Availability', default='available', tracking=True)
    max_weekly_hours = fields.Float(string='Max Weekly Hours', default=40.0)

    # ─────────────────────────────────────────────
    # Timesheets & Utilization
    # ─────────────────────────────────────────────
    timesheet_ids = fields.One2many(
        'consultpro.timesheet',
        'consultant_id',
        string='Timesheets',
    )
    total_logged_hours = fields.Float(
        string='Total Logged Hours',
        compute='_compute_utilization',
        store=True,
    )
    current_month_hours = fields.Float(
        string='This Month Hours',
        compute='_compute_utilization',
        store=True,
    )
    utilization_rate = fields.Float(
        string='Utilization Rate (%)',
        compute='_compute_utilization',
        store=True,
    )

    # ─────────────────────────────────────────────
    # Projects
    # ─────────────────────────────────────────────
    project_ids = fields.Many2many(
        'consultpro.project',
        'project_consultant_rel',
        'consultant_id', 'project_id',
        string='Assigned Projects',
    )
    active_project_count = fields.Integer(
        compute='_compute_active_project_count',
        string='Active Projects',
    )

    # ─────────────────────────────────────────────
    # Computes
    # ─────────────────────────────────────────────
    @api.depends('employee_id')
    def _compute_name(self):
        for rec in self:
            rec.name = rec.employee_id.name if rec.employee_id else ''

    @api.depends('timesheet_ids.hours', 'timesheet_ids.state', 'timesheet_ids.date')
    def _compute_utilization(self):
        import datetime
        today = fields.Date.today()
        first_day = today.replace(day=1)
        for rec in self:
            approved_sheets = rec.timesheet_ids.filtered(
                lambda t: t.state == 'approved'
            )
            rec.total_logged_hours = sum(approved_sheets.mapped('hours'))
            this_month = approved_sheets.filtered(
                lambda t: t.date >= first_day and t.date <= today
            )
            rec.current_month_hours = sum(this_month.mapped('hours'))
            # Utilization: current month hours vs available capacity
            capacity = rec.max_weekly_hours * 4  # approx monthly
            rec.utilization_rate = (
                (rec.current_month_hours / capacity * 100) if capacity else 0.0
            )

    @api.depends('project_ids.state')
    def _compute_active_project_count(self):
        for rec in self:
            rec.active_project_count = len(
                rec.project_ids.filtered(lambda p: p.state == 'in_progress')
            )

    # ─────────────────────────────────────────────
    # ORM
    # ─────────────────────────────────────────────
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('code', 'New') == 'New':
                vals['code'] = self.env['ir.sequence'].next_by_code(
                    'consultpro.consultant'
                ) or 'CON-0001'
        return super().create(vals_list)

    @api.constrains('employee_id')
    def _check_unique_employee(self):
        for rec in self:
            if self.search_count([
                ('employee_id', '=', rec.employee_id.id),
                ('id', '!=', rec.id),
            ]) > 0:
                raise ValidationError(_(
                    "Employee '%s' is already registered as a consultant."
                ) % rec.employee_id.name)

    def action_view_timesheets(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Timesheets'),
            'res_model': 'consultpro.timesheet',
            'view_mode': 'list,form',
            'domain': [('consultant_id', '=', self.id)],
            'context': {'default_consultant_id': self.id},
        }