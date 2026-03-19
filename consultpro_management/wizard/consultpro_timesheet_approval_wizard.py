# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class ConsultProTimesheetApprovalWizard(models.TransientModel):
    _name = 'consultpro.timesheet.approval.wizard'
    _description = 'Bulk Timesheet Approval Wizard'

    action = fields.Selection([
        ('approve', 'Approve'),
        ('reject', 'Reject'),
    ], string='Action', required=True, default='approve')

    rejection_reason = fields.Text(string='Rejection Reason')

    timesheet_line_ids = fields.One2many(
        'consultpro.timesheet.approval.wizard.line',
        'wizard_id',
        string='Timesheets',
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
        'res.currency',
        default=lambda self: self.env.company.currency_id,
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        active_ids = self.env.context.get('active_ids', [])
        if active_ids:
            timesheets = self.env['consultpro.timesheet'].browse(active_ids).filtered(
                lambda t: t.state == 'submitted'
            )
            lines = []
            for ts in timesheets:
                lines.append((0, 0, {
                    'timesheet_id': ts.id,
                    'consultant_id': ts.consultant_id.id,
                    'project_id': ts.project_id.id,
                    'date': ts.date,
                    'description': ts.name,
                    'hours': ts.hours,
                    'amount': ts.amount,
                    'include': True,
                }))
            res['timesheet_line_ids'] = lines
        return res

    @api.depends('timesheet_line_ids.hours', 'timesheet_line_ids.amount', 'timesheet_line_ids.include')
    def _compute_totals(self):
        for rec in self:
            selected = rec.timesheet_line_ids.filtered('include')
            rec.total_hours = sum(selected.mapped('hours'))
            rec.total_amount = sum(selected.mapped('amount'))

    @api.onchange('action')
    def _onchange_action(self):
        if self.action == 'approve':
            self.rejection_reason = False

    def action_confirm(self):
        self.ensure_one()
        selected_lines = self.timesheet_line_ids.filtered('include')
        if not selected_lines:
            raise UserError(_("Please select at least one timesheet."))

        timesheets = selected_lines.mapped('timesheet_id')

        if self.action == 'approve':
            timesheets.action_approve()
            # Send approval notifications
            for ts in timesheets:
                self.env['consultpro.notification.service'].notify_timesheet_approved(ts)
            message = _("%d timesheet(s) approved successfully.") % len(timesheets)
        else:
            if not self.rejection_reason:
                raise UserError(_("Please provide a rejection reason."))
            timesheets.action_reject(reason=self.rejection_reason)
            for ts in timesheets:
                self.env['consultpro.notification.service'].notify_timesheet_rejected(ts)
            message = _("%d timesheet(s) rejected.") % len(timesheets)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': message,
                'type': 'success',
                'sticky': False,
            },
        }


class ConsultProTimesheetApprovalWizardLine(models.TransientModel):
    _name = 'consultpro.timesheet.approval.wizard.line'
    _description = 'Timesheet Approval Wizard Line'
    _order = 'date'

    wizard_id = fields.Many2one(
        'consultpro.timesheet.approval.wizard',
        ondelete='cascade',
    )
    timesheet_id = fields.Many2one('consultpro.timesheet', readonly=True)
    consultant_id = fields.Many2one('consultpro.consultant', string='Consultant', readonly=True)
    project_id = fields.Many2one('consultpro.project', string='Project', readonly=True)
    date = fields.Date(string='Date', readonly=True)
    description = fields.Char(string='Description', readonly=True)
    hours = fields.Float(string='Hours', readonly=True)
    currency_id = fields.Many2one(related='wizard_id.currency_id')
    amount = fields.Monetary(string='Amount', readonly=True, currency_field='currency_id')
    include = fields.Boolean(string='Select', default=True)