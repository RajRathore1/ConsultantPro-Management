# -*- coding: utf-8 -*-
from odoo import models, api, fields, _
from odoo.exceptions import UserError


class ConsultProBillingService(models.AbstractModel):
    """
    Service layer for invoice generation logic.
    Keeps wizard and model layers thin.
    """
    _name = 'consultpro.billing.service'
    _description = 'ConsultPro Billing Service'

    @api.model
    def generate_invoice_from_timesheets(
        self,
        project_id,
        timesheet_ids,
        date_from=None,
        date_to=None,
        group_by='consultant',
    ):
        """
        Generate a draft account.move (invoice) from approved timesheets.

        :param project_id: int — consultpro.project id
        :param timesheet_ids: list[int] — consultpro.timesheet ids
        :param date_from: date or None
        :param date_to: date or None
        :param group_by: 'consultant' | 'task' | 'activity' | 'single'
        :return: account.move record
        """
        project = self.env['consultpro.project'].browse(project_id)
        if not project.exists():
            raise UserError(_("Project not found."))

        timesheets = self.env['consultpro.timesheet'].browse(timesheet_ids).filtered(
            lambda t: t.state == 'approved' and t.billable and not t.invoice_id
        )
        if not timesheets:
            raise UserError(_("No billable approved timesheets found to invoice."))

        invoice_lines = self._build_invoice_lines(timesheets, group_by)

        invoice_vals = {
            'move_type': 'out_invoice',
            'partner_id': project.client_id.partner_id.id,
            'invoice_date': fields.Date.today(),
            'invoice_date_due': fields.Date.today(),
            'consultpro_project_id': project.id,
            'consultpro_contract_id': project.contract_id.id if project.contract_id else False,
            'is_consultpro_invoice': True,
            'period_from': date_from or (timesheets.mapped('date') and min(timesheets.mapped('date'))),
            'period_to': date_to or (timesheets.mapped('date') and max(timesheets.mapped('date'))),
            'invoice_line_ids': invoice_lines,
            'narration': _(
                "Invoice for services rendered on project: %s\nPeriod: %s to %s"
            ) % (
                project.name,
                str(date_from or ''),
                str(date_to or ''),
            ),
        }

        if project.contract_id and project.contract_id.payment_terms_id:
            invoice_vals['invoice_payment_term_id'] = project.contract_id.payment_terms_id.id

        if project.analytic_account_id:
            invoice_vals['invoice_line_ids'] = [
                (0, 0, {**line[2], 'analytic_distribution': {
                    str(project.analytic_account_id.id): 100
                }})
                if line[0] == 0 else line
                for line in invoice_lines
            ]

        invoice = self.env['account.move'].create(invoice_vals)

        # Link timesheets to invoice
        timesheets.write({'invoice_id': invoice.id})

        # Create consultpro.invoice audit record
        self.env['consultpro.invoice'].create({
            'move_id': invoice.id,
            'project_id': project.id,
            'period_from': invoice_vals.get('period_from'),
            'period_to': invoice_vals.get('period_to'),
            'timesheet_ids': [(6, 0, timesheets.ids)],
        })

        return invoice

    def _build_invoice_lines(self, timesheets, group_by):
        """Build (0, 0, vals) tuples for invoice lines based on grouping."""
        lines = []

        if group_by == 'consultant':
            groups = {}
            for ts in timesheets:
                key = ts.consultant_id.id
                groups.setdefault(key, self.env['consultpro.timesheet'])
                groups[key] |= ts
            for consultant_id, ts_group in groups.items():
                consultant = ts_group[0].consultant_id
                total_hours = sum(ts_group.mapped('hours'))
                rate = consultant.billing_rate
                product = self._get_service_product(ts_group[0].project_id)
                lines.append((0, 0, {
                    'name': _(
                        "Consulting Services — %s (%s hrs)"
                    ) % (consultant.name, total_hours),
                    'product_id': product.id if product else False,
                    'quantity': total_hours,
                    'price_unit': rate,
                }))

        elif group_by == 'task':
            groups = {}
            for ts in timesheets:
                key = ts.task_id.id if ts.task_id else 0
                groups.setdefault(key, self.env['consultpro.timesheet'])
                groups[key] |= ts
            for task_id, ts_group in groups.items():
                task_name = ts_group[0].task_id.name if ts_group[0].task_id else _('General')
                total_hours = sum(ts_group.mapped('hours'))
                avg_rate = (
                    sum(ts.hours * ts.billing_rate for ts in ts_group) / total_hours
                    if total_hours else 0.0
                )
                product = self._get_service_product(ts_group[0].project_id)
                lines.append((0, 0, {
                    'name': _("Task: %s (%s hrs)") % (task_name, total_hours),
                    'product_id': product.id if product else False,
                    'quantity': total_hours,
                    'price_unit': avg_rate,
                }))

        elif group_by == 'activity':
            groups = {}
            for ts in timesheets:
                key = ts.activity_type
                groups.setdefault(key, self.env['consultpro.timesheet'])
                groups[key] |= ts
            activity_labels = dict(
                self.env['consultpro.timesheet']._fields['activity_type'].selection
            )
            for activity, ts_group in groups.items():
                total_hours = sum(ts_group.mapped('hours'))
                avg_rate = (
                    sum(ts.hours * ts.billing_rate for ts in ts_group) / total_hours
                    if total_hours else 0.0
                )
                product = self._get_service_product(ts_group[0].project_id)
                lines.append((0, 0, {
                    'name': _("%s (%s hrs)") % (activity_labels.get(activity, activity), total_hours),
                    'product_id': product.id if product else False,
                    'quantity': total_hours,
                    'price_unit': avg_rate,
                }))

        else:  # single line
            total_hours = sum(timesheets.mapped('hours'))
            total_amount = sum(ts.hours * ts.billing_rate for ts in timesheets)
            avg_rate = total_amount / total_hours if total_hours else 0.0
            project = timesheets[0].project_id
            product = self._get_service_product(project)
            lines.append((0, 0, {
                'name': _("Professional Services — %s") % project.name,
                'product_id': product.id if product else False,
                'quantity': total_hours,
                'price_unit': avg_rate,
            }))

        return lines

    def _get_service_product(self, project):
        """Find or create a default service product for invoicing."""
        if project.contract_id and project.contract_id.service_ids:
            svc = project.contract_id.service_ids[0]
            if svc.product_id:
                return svc.product_id
        # Fallback: find generic service product
        return self.env['product.product'].search(
            [('type', '=', 'service'), ('active', '=', True)],
            limit=1,
        )

    @api.model
    def compute_project_profitability(self, project_id):
        """Return profitability metrics for a project."""
        project = self.env['consultpro.project'].browse(project_id)
        approved_ts = project.timesheet_ids.filtered(lambda t: t.state == 'approved')

        revenue = sum(ts.hours * ts.billing_rate for ts in approved_ts if ts.billable)
        cost = sum(ts.hours * (ts.consultant_id.cost_rate or 0) for ts in approved_ts)
        gross_profit = revenue - cost
        margin = (gross_profit / revenue * 100) if revenue else 0.0

        return {
            'project': project.name,
            'total_hours': sum(approved_ts.mapped('hours')),
            'billable_hours': sum(approved_ts.filtered('billable').mapped('hours')),
            'revenue': revenue,
            'cost': cost,
            'gross_profit': gross_profit,
            'margin_pct': round(margin, 2),
            'budget': project.budget,
            'budget_utilization': round(cost / project.budget * 100, 2) if project.budget else 0.0,
        }