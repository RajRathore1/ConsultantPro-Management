# -*- coding: utf-8 -*-
from odoo import http, _
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager
from odoo.exceptions import AccessError, MissingError


class ConsultProPortalController(CustomerPortal):

    # ─────────────────────────────────────────────
    # Portal Home Count
    # ─────────────────────────────────────────────
    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        partner = request.env.user.partner_id

        if 'project_count' in counters:
            values['project_count'] = request.env['consultpro.project'].search_count(
                self._get_portal_project_domain(partner)
            )
        if 'invoice_count' in counters:
            values['invoice_count'] = request.env['account.move'].search_count(
                self._get_portal_invoice_domain(partner)
            )
        return values

    def _get_portal_project_domain(self, partner):
        return [
            ('client_id.partner_id', '=', partner.commercial_partner_id.id),
            ('state', 'not in', ['draft', 'cancelled']),
        ]

    def _get_portal_invoice_domain(self, partner):
        return [
            ('partner_id', '=', partner.commercial_partner_id.id),
            ('move_type', '=', 'out_invoice'),
            ('state', '=', 'posted'),
            ('is_consultpro_invoice', '=', True),
        ]

    # ─────────────────────────────────────────────
    # Projects List
    # ─────────────────────────────────────────────
    @http.route([
        '/my/consultpro/projects',
        '/my/consultpro/projects/page/<int:page>',
    ], type='http', auth='user', website=True)
    def portal_projects(self, page=1, sortby='date_start', filterby='all', **kwargs):
        partner = request.env.user.partner_id
        Project = request.env['consultpro.project']

        domain = self._get_portal_project_domain(partner)

        searchbar_sortings = {
            'date_start': {'label': _('Start Date'), 'order': 'date_start desc'},
            'name': {'label': _('Name'), 'order': 'name asc'},
            'state': {'label': _('Status'), 'order': 'state'},
        }
        searchbar_filters = {
            'all': {'label': _('All'), 'domain': []},
            'in_progress': {'label': _('In Progress'), 'domain': [('state', '=', 'in_progress')]},
            'done': {'label': _('Completed'), 'domain': [('state', '=', 'done')]},
        }

        if filterby in searchbar_filters:
            domain += searchbar_filters[filterby]['domain']

        order = searchbar_sortings.get(sortby, searchbar_sortings['date_start'])['order']
        project_count = Project.search_count(domain)

        pager = portal_pager(
            url='/my/consultpro/projects',
            url_args={'sortby': sortby, 'filterby': filterby},
            total=project_count,
            page=page,
            step=10,
        )

        projects = Project.search(
            domain,
            order=order,
            limit=10,
            offset=pager['offset'],
        )

        return request.render('consultpro_management.portal_my_projects', {
            'projects': projects,
            'pager': pager,
            'sortby': sortby,
            'filterby': filterby,
            'searchbar_sortings': searchbar_sortings,
            'searchbar_filters': searchbar_filters,
            'page_name': 'project',
        })

    # ─────────────────────────────────────────────
    # Project Detail
    # ─────────────────────────────────────────────
    @http.route('/my/consultpro/projects/<int:project_id>', type='http', auth='user', website=True)
    def portal_project_detail(self, project_id, **kwargs):
        partner = request.env.user.partner_id
        try:
            project = request.env['consultpro.project'].browse(project_id)
            if project.client_id.partner_id.commercial_partner_id != partner.commercial_partner_id:
                raise AccessError(_("Access denied."))
        except (AccessError, MissingError):
            return request.redirect('/my/consultpro/projects')

        # Approved timesheets for client view (summary only)
        approved_ts = project.timesheet_ids.filtered(lambda t: t.state == 'approved' and t.billable)
        ts_by_consultant = {}
        for ts in approved_ts:
            name = ts.consultant_id.name
            ts_by_consultant.setdefault(name, 0.0)
            ts_by_consultant[name] += ts.hours

        return request.render('consultpro_management.portal_project_detail', {
            'project': project,
            'tasks': project.task_ids.filtered(lambda t: t.state != 'cancelled'),
            'total_logged_hours': sum(approved_ts.mapped('hours')),
            'ts_by_consultant': ts_by_consultant,
            'page_name': 'project',
        })

    # ─────────────────────────────────────────────
    # Invoices List
    # ─────────────────────────────────────────────
    @http.route([
        '/my/consultpro/invoices',
        '/my/consultpro/invoices/page/<int:page>',
    ], type='http', auth='user', website=True)
    def portal_invoices(self, page=1, **kwargs):
        partner = request.env.user.partner_id
        domain = self._get_portal_invoice_domain(partner)

        invoice_count = request.env['account.move'].search_count(domain)
        pager = portal_pager(
            url='/my/consultpro/invoices',
            total=invoice_count,
            page=page,
            step=10,
        )
        invoices = request.env['account.move'].search(
            domain,
            order='invoice_date desc',
            limit=10,
            offset=pager['offset'],
        )
        return request.render('consultpro_management.portal_my_invoices', {
            'invoices': invoices,
            'pager': pager,
            'page_name': 'invoice',
        })