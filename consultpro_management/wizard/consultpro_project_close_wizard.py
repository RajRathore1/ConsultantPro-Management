# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class ConsultProProjectCloseWizard(models.TransientModel):
    _name = 'consultpro.project.close.wizard'
    _description = 'Project Closure Wizard'

    project_id = fields.Many2one(
        'consultpro.project',
        string='Project',
        required=True,
        default=lambda self: self.env.context.get('active_id'),
    )
    client_id = fields.Many2one(related='project_id.client_id', readonly=True)
    state = fields.Selection(related='project_id.state', readonly=True)

    # Closure details
    close_notes = fields.Html(string='Closure Notes / Summary')
    lessons_learned = fields.Text(string='Lessons Learned')
    client_satisfaction = fields.Selection([
        ('1', '1 — Very Dissatisfied'),
        ('2', '2 — Dissatisfied'),
        ('3', '3 — Neutral'),
        ('4', '4 — Satisfied'),
        ('5', '5 — Very Satisfied'),
    ], string='Client Satisfaction')
    send_client_notification = fields.Boolean(
        string='Notify Client?',
        default=True,
    )
    generate_final_invoice = fields.Boolean(
        string='Generate Final Invoice?',
        default=False,
    )

    # Blocking issues
    open_task_count = fields.Integer(
        string='Open Tasks',
        compute='_compute_blocking',
    )
    pending_timesheet_count = fields.Integer(
        string='Pending Timesheets',
        compute='_compute_blocking',
    )
    uninvoiced_hours = fields.Float(
        string='Un-invoiced Approved Hours',
        compute='_compute_blocking',
    )
    has_blocking_issues = fields.Boolean(
        compute='_compute_blocking',
    )
    blocking_summary = fields.Text(
        compute='_compute_blocking',
        string='Blocking Issues',
    )

    @api.depends('project_id')
    def _compute_blocking(self):
        for rec in self:
            if not rec.project_id:
                rec.open_task_count = 0
                rec.pending_timesheet_count = 0
                rec.uninvoiced_hours = 0.0
                rec.has_blocking_issues = False
                rec.blocking_summary = ''
                continue

            open_tasks = rec.project_id.task_ids.filtered(
                lambda t: t.state not in ('done', 'cancelled')
            )
            pending_ts = rec.project_id.timesheet_ids.filtered(
                lambda t: t.state in ('draft', 'submitted')
            )
            uninvoiced = rec.project_id.timesheet_ids.filtered(
                lambda t: t.state == 'approved' and t.billable and not t.invoice_id
            )

            rec.open_task_count = len(open_tasks)
            rec.pending_timesheet_count = len(pending_ts)
            rec.uninvoiced_hours = sum(uninvoiced.mapped('hours'))
            rec.has_blocking_issues = bool(open_tasks or pending_ts)

            issues = []
            if open_tasks:
                issues.append(_("• %d open task(s)") % len(open_tasks))
            if pending_ts:
                issues.append(_("• %d pending timesheet(s)") % len(pending_ts))
            rec.blocking_summary = '\n'.join(issues) if issues else _("None — project is ready to close.")

    def action_close_project(self):
        self.ensure_one()

        if self.has_blocking_issues:
            raise UserError(_(
                "Cannot close project. Please resolve the following issues first:\n%s"
            ) % self.blocking_summary)

        # Save lessons learned as internal note
        notes = self.close_notes or ''
        if self.lessons_learned:
            notes += f"\n\n<b>{_('Lessons Learned')}</b><br/>{self.lessons_learned}"
        if self.client_satisfaction:
            satisfaction_labels = dict(
                self._fields['client_satisfaction'].selection
            )
            notes += f"\n\n<b>{_('Client Satisfaction')}</b>: {satisfaction_labels.get(self.client_satisfaction, '')}"

        self.env['consultpro.project.service'].close_project(
            project_id=self.project_id.id,
            close_notes=notes,
            send_notification=self.send_client_notification,
        )

        # Optional: trigger final invoice wizard
        if self.generate_final_invoice and self.uninvoiced_hours > 0:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Generate Final Invoice'),
                'res_model': 'consultpro.invoice.wizard',
                'view_mode': 'form',
                'target': 'new',
                'context': {
                    'active_model': 'consultpro.project',
                    'active_id': self.project_id.id,
                },
            }

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Project Closed'),
                'message': _("Project '%s' has been successfully closed.") % self.project_id.name,
                'type': 'success',
                'sticky': False,
            },
        }