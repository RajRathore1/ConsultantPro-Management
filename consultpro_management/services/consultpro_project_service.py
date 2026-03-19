# -*- coding: utf-8 -*-
from odoo import models, api, fields, _
from odoo.exceptions import UserError


class ConsultProProjectService(models.AbstractModel):
    _name = 'consultpro.project.service'
    _description = 'ConsultPro Project Business Logic Service'

    @api.model
    def close_project(self, project_id, close_notes=None, send_notification=True):
        """
        Safely close a project:
        1. Validate all tasks are done/cancelled
        2. Validate no un-approved timesheets
        3. Transition state to 'done'
        4. Send client notification if requested
        """
        project = self.env['consultpro.project'].browse(project_id)
        if not project.exists():
            raise UserError(_("Project not found."))

        # Guard: open tasks
        open_tasks = project.task_ids.filtered(
            lambda t: t.state not in ('done', 'cancelled')
        )
        if open_tasks:
            raise UserError(_(
                "Cannot close project '%s'. %d task(s) are still open:\n%s"
            ) % (
                project.name,
                len(open_tasks),
                '\n'.join('• ' + t.name for t in open_tasks),
            ))

        # Guard: pending timesheets
        pending_ts = project.timesheet_ids.filtered(
            lambda t: t.state in ('draft', 'submitted')
        )
        if pending_ts:
            raise UserError(_(
                "Cannot close project '%s'. %d timesheet(s) are not yet approved."
            ) % (project.name, len(pending_ts)))

        project.write({
            'state': 'done',
            'actual_end_date': fields.Date.today(),
        })

        if close_notes:
            project.message_post(
                body=close_notes,
                subject=_("Project Closure Notes"),
            )

        if send_notification:
            self.env['consultpro.notification.service'].notify_project_closed(project)

        return True

    @api.model
    def get_project_health(self, project_id):
        """
        Return a health score (0–100) and risk flags for a project.
        """
        project = self.env['consultpro.project'].browse(project_id)
        flags = []
        score = 100

        # Schedule risk
        if project.days_remaining < 0:
            flags.append({'type': 'danger', 'msg': _("Project is overdue.")})
            score -= 30
        elif project.days_remaining < 7:
            flags.append({'type': 'warning', 'msg': _("Project ends in less than 7 days.")})
            score -= 10

        # Budget risk
        if project.is_over_budget:
            flags.append({'type': 'danger', 'msg': _("Project is over budget.")})
            score -= 25
        elif project.budget and project.budget_spent / project.budget > 0.85:
            flags.append({'type': 'warning', 'msg': _("Budget 85%+ consumed.")})
            score -= 10

        # Task completion
        if project.task_count and project.completion_rate < 50 and project.days_remaining < 14:
            flags.append({'type': 'warning', 'msg': _("Low task completion with tight deadline.")})
            score -= 15

        # Overdue tasks
        overdue_count = len(project.task_ids.filtered('is_overdue'))
        if overdue_count > 0:
            flags.append({'type': 'warning', 'msg': _(f"{overdue_count} overdue task(s).")})
            score -= (5 * min(overdue_count, 4))

        # Pending approvals
        pending_ts = project.timesheet_ids.filtered(lambda t: t.state == 'submitted')
        if len(pending_ts) > 10:
            flags.append({'type': 'info', 'msg': _("Many timesheets awaiting approval.")})
            score -= 5

        return {
            'score': max(0, score),
            'label': (
                'Healthy' if score >= 75 else
                'At Risk' if score >= 50 else
                'Critical'
            ),
            'flags': flags,
        }

    @api.model
    def assign_consultant(self, project_id, consultant_id, check_availability=True):
        """Add a consultant to a project with optional availability check."""
        project = self.env['consultpro.project'].browse(project_id)
        consultant = self.env['consultpro.consultant'].browse(consultant_id)

        if check_availability and consultant.availability == 'booked':
            raise UserError(_(
                "Consultant '%s' is fully booked and cannot be assigned."
            ) % consultant.name)

        if consultant not in project.consultant_ids:
            project.consultant_ids = [(4, consultant.id)]
            project.message_post(
                body=_("Consultant <b>%s</b> assigned to project.") % consultant.name,
            )

        # Auto-update availability
        if len(consultant.project_ids.filtered(lambda p: p.state == 'in_progress')) >= 3:
            consultant.availability = 'booked'
        elif len(consultant.project_ids.filtered(lambda p: p.state == 'in_progress')) >= 1:
            consultant.availability = 'partially'

        return True