# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class ConsultProDashboard(models.Model):
    """
    Transient-like model providing KPI aggregates for the dashboard.
    Used by OWL dashboard component via JSON-RPC controller.
    """
    _name = 'consultpro.dashboard'
    _description = 'ConsultPro KPI Dashboard'
    _auto = False  # No DB table — we use @api.model methods only

    # ─────────────────────────────────────────────
    # Public API (called by dashboard controller)
    # ─────────────────────────────────────────────

    @api.model
    def get_kpi_data(self):
        """Return top-level KPI numbers for the dashboard header cards."""
        today = fields.Date.today()
        first_of_month = today.replace(day=1)

        active_clients = self.env['consultpro.client'].search_count(
            [('state', '=', 'active')]
        )
        active_contracts = self.env['consultpro.contract'].search_count(
            [('state', '=', 'active')]
        )
        active_projects = self.env['consultpro.project'].search_count(
            [('state', '=', 'in_progress')]
        )
        open_tasks = self.env['consultpro.task'].search_count(
            [('state', 'in', ('todo', 'in_progress', 'review'))]
        )
        pending_timesheets = self.env['consultpro.timesheet'].search_count(
            [('state', '=', 'submitted')]
        )
        overdue_tasks = self.env['consultpro.task'].search_count(
            [('is_overdue', '=', True)]
        )
        overdue_contracts = self.env['consultpro.contract'].search_count(
            [('is_overdue', '=', True)]
        )

        # Revenue this month
        invoices = self.env['account.move'].search([
            ('move_type', '=', 'out_invoice'),
            ('state', '=', 'posted'),
            ('is_consultpro_invoice', '=', True),
            ('invoice_date', '>=', str(first_of_month)),
            ('invoice_date', '<=', str(today)),
        ])
        revenue_this_month = sum(invoices.mapped('amount_total'))

        # Utilization avg
        consultants = self.env['consultpro.consultant'].search([('active', '=', True)])
        avg_utilization = (
            sum(consultants.mapped('utilization_rate')) / len(consultants)
            if consultants else 0.0
        )

        return {
            'active_clients': active_clients,
            'active_contracts': active_contracts,
            'active_projects': active_projects,
            'open_tasks': open_tasks,
            'pending_timesheets': pending_timesheets,
            'overdue_tasks': overdue_tasks,
            'overdue_contracts': overdue_contracts,
            'revenue_this_month': revenue_this_month,
            'avg_utilization': round(avg_utilization, 1),
        }

    @api.model
    def get_project_status_chart(self):
        """Pie/donut chart data: projects by state."""
        states = ['draft', 'planning', 'in_progress', 'on_hold', 'review', 'done', 'cancelled']
        labels = {
            'draft': 'Draft', 'planning': 'Planning', 'in_progress': 'In Progress',
            'on_hold': 'On Hold', 'review': 'Under Review',
            'done': 'Completed', 'cancelled': 'Cancelled',
        }
        Project = self.env['consultpro.project']
        return [
            {'label': labels[s], 'value': Project.search_count([('state', '=', s)])}
            for s in states
        ]

    @api.model
    def get_revenue_trend(self, months=6):
        """Bar chart: monthly revenue for last N months."""
        from dateutil.relativedelta import relativedelta
        today = fields.Date.today()
        result = []
        for i in range(months - 1, -1, -1):
            month_start = (today.replace(day=1) - relativedelta(months=i))
            month_end = month_start + relativedelta(months=1, days=-1)
            invoices = self.env['account.move'].search([
                ('move_type', '=', 'out_invoice'),
                ('state', '=', 'posted'),
                ('is_consultpro_invoice', '=', True),
                ('invoice_date', '>=', str(month_start)),
                ('invoice_date', '<=', str(month_end)),
            ])
            result.append({
                'month': month_start.strftime('%b %Y'),
                'revenue': sum(invoices.mapped('amount_total')),
            })
        return result

    @api.model
    def get_consultant_utilization(self):
        """Table data: top consultants by utilization."""
        consultants = self.env['consultpro.consultant'].search(
            [('active', '=', True)],
            order='utilization_rate desc',
            limit=10,
        )
        return [{
            'name': c.name,
            'seniority': c.seniority,
            'utilization_rate': round(c.utilization_rate, 1),
            'current_month_hours': c.current_month_hours,
            'availability': c.availability,
            'active_projects': c.active_project_count,
        } for c in consultants]

    @api.model
    def get_recent_activity(self, limit=20):
        """Activity feed: recent timesheet submissions, project updates etc."""
        activities = []

        # Recent submitted timesheets
        timesheets = self.env['consultpro.timesheet'].search(
            [('state', '=', 'submitted')],
            order='write_date desc',
            limit=limit // 2,
        )
        for ts in timesheets:
            activities.append({
                'type': 'timesheet',
                'icon': 'fa-clock-o',
                'message': f"{ts.consultant_id.name} submitted {ts.hours}h for '{ts.project_id.name}'",
                'date': str(ts.date),
            })

        # Recent project status changes
        projects = self.env['consultpro.project'].search(
            [],
            order='write_date desc',
            limit=limit // 2,
        )
        for proj in projects:
            activities.append({
                'type': 'project',
                'icon': 'fa-briefcase',
                'message': f"Project '{proj.name}' is {proj.state}",
                'date': str(proj.write_date.date() if proj.write_date else ''),
            })

        return sorted(activities, key=lambda x: x['date'], reverse=True)[:limit]