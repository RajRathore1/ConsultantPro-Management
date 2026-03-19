# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ConsultProTask(models.Model):
    _name = 'consultpro.task'
    _description = 'ConsultPro Task'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'
    _order = 'sequence, priority desc, date_deadline'

    # ─────────────────────────────────────────────
    # Core
    # ─────────────────────────────────────────────
    name = fields.Char(string='Task Title', required=True, tracking=True)
    sequence = fields.Integer(default=10)
    project_id = fields.Many2one(
        'consultpro.project',
        string='Project',
        required=True,
        ondelete='cascade',
        index=True,
        tracking=True,
    )
    client_id = fields.Many2one(
        related='project_id.client_id',
        string='Client',
        store=True,
    )
    parent_task_id = fields.Many2one(
        'consultpro.task',
        string='Parent Task',
        ondelete='cascade',
        index=True,
    )
    child_task_ids = fields.One2many(
        'consultpro.task',
        'parent_task_id',
        string='Sub-tasks',
    )

    state = fields.Selection([
        ('todo', 'To Do'),
        ('in_progress', 'In Progress'),
        ('review', 'In Review'),
        ('done', 'Done'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='todo', tracking=True, required=True, index=True)

    priority = fields.Selection([
        ('0', 'Normal'),
        ('1', 'High'),
        ('2', 'Urgent'),
    ], string='Priority', default='0')

    task_type = fields.Selection([
        ('deliverable', 'Deliverable'),
        ('meeting', 'Meeting'),
        ('research', 'Research'),
        ('review', 'Review'),
        ('admin', 'Administrative'),
        ('other', 'Other'),
    ], string='Task Type', default='deliverable')

    # ─────────────────────────────────────────────
    # Assignment & Dates
    # ─────────────────────────────────────────────
    assigned_to_id = fields.Many2one(
        'consultpro.consultant',
        string='Assigned To',
        tracking=True,
        index=True,
    )
    reviewer_id = fields.Many2one(
        'res.users',
        string='Reviewer',
    )
    date_start = fields.Date(string='Start Date')
    date_deadline = fields.Date(string='Deadline', tracking=True)
    date_done = fields.Datetime(string='Completed On', readonly=True)

    # ─────────────────────────────────────────────
    # Hours
    # ─────────────────────────────────────────────
    estimated_hours = fields.Float(string='Estimated Hours', default=0.0)
    logged_hours = fields.Float(
        string='Logged Hours',
        compute='_compute_logged_hours',
        store=True,
    )
    remaining_hours = fields.Float(
        string='Remaining Hours',
        compute='_compute_remaining_hours',
    )
    progress = fields.Float(
        string='Progress (%)',
        compute='_compute_progress',
        store=True,
    )

    # ─────────────────────────────────────────────
    # Content
    # ─────────────────────────────────────────────
    description = fields.Html(string='Description')
    acceptance_criteria = fields.Text(string='Acceptance Criteria')
    tag_ids = fields.Many2many(
        'project.tags',
        string='Tags',
    )

    # ─────────────────────────────────────────────
    # Timesheets
    # ─────────────────────────────────────────────
    timesheet_ids = fields.One2many(
        'consultpro.timesheet',
        'task_id',
        string='Timesheets',
    )
    timesheet_count = fields.Integer(
        compute='_compute_timesheet_count',
        string='Timesheets',
    )
    is_overdue = fields.Boolean(
        compute='_compute_is_overdue',
        store=True,
        string='Overdue',
    )

    # ─────────────────────────────────────────────
    # Computes
    # ─────────────────────────────────────────────
    @api.depends('timesheet_ids.hours', 'timesheet_ids.state')
    def _compute_logged_hours(self):
        for rec in self:
            approved = rec.timesheet_ids.filtered(lambda t: t.state == 'approved')
            rec.logged_hours = sum(approved.mapped('hours'))

    @api.depends('estimated_hours', 'logged_hours')
    def _compute_remaining_hours(self):
        for rec in self:
            rec.remaining_hours = max(0.0, rec.estimated_hours - rec.logged_hours)

    @api.depends('estimated_hours', 'logged_hours', 'state')
    def _compute_progress(self):
        for rec in self:
            if rec.state == 'done':
                rec.progress = 100.0
            elif rec.estimated_hours > 0:
                rec.progress = min(100.0, rec.logged_hours / rec.estimated_hours * 100)
            else:
                rec.progress = 0.0

    @api.depends('timesheet_ids')
    def _compute_timesheet_count(self):
        for rec in self:
            rec.timesheet_count = len(rec.timesheet_ids)

    @api.depends('date_deadline', 'state')
    def _compute_is_overdue(self):
        today = fields.Date.today()
        for rec in self:
            rec.is_overdue = (
                rec.state not in ('done', 'cancelled')
                and rec.date_deadline
                and rec.date_deadline < today
            )

    # ─────────────────────────────────────────────
    # ORM
    # ─────────────────────────────────────────────
    def write(self, vals):
        if vals.get('state') == 'done' and 'date_done' not in vals:
            vals['date_done'] = fields.Datetime.now()
        return super().write(vals)

    @api.constrains('date_start', 'date_deadline')
    def _check_dates(self):
        for rec in self:
            if rec.date_start and rec.date_deadline and rec.date_start > rec.date_deadline:
                raise ValidationError(_("Deadline must be after start date."))

    # ─────────────────────────────────────────────
    # State Actions
    # ─────────────────────────────────────────────
    def action_start(self):
        self.write({'state': 'in_progress'})

    def action_submit_review(self):
        self.write({'state': 'review'})

    def action_mark_done(self):
        self.write({'state': 'done'})

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    def action_reopen(self):
        self.write({'state': 'todo', 'date_done': False})