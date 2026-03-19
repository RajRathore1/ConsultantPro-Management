# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
from odoo.exceptions import AccessError
import json


class ConsultProDashboardController(http.Controller):

    @http.route('/consultpro/dashboard/kpis', type='json', auth='user', methods=['POST'])
    def get_kpis(self, **kwargs):
        """Return KPI card data for the dashboard header."""
        try:
            data = request.env['consultpro.dashboard'].get_kpi_data()
            return {'status': 'ok', 'data': data}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

    @http.route('/consultpro/dashboard/project_status', type='json', auth='user', methods=['POST'])
    def get_project_status_chart(self, **kwargs):
        """Return project-by-status chart data."""
        try:
            data = request.env['consultpro.dashboard'].get_project_status_chart()
            return {'status': 'ok', 'data': data}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

    @http.route('/consultpro/dashboard/revenue_trend', type='json', auth='user', methods=['POST'])
    def get_revenue_trend(self, months=6, **kwargs):
        """Return monthly revenue bar chart data."""
        try:
            data = request.env['consultpro.dashboard'].get_revenue_trend(months=int(months))
            return {'status': 'ok', 'data': data}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

    @http.route('/consultpro/dashboard/utilization', type='json', auth='user', methods=['POST'])
    def get_consultant_utilization(self, **kwargs):
        """Return consultant utilization table data."""
        try:
            data = request.env['consultpro.dashboard'].get_consultant_utilization()
            return {'status': 'ok', 'data': data}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

    @http.route('/consultpro/dashboard/activity', type='json', auth='user', methods=['POST'])
    def get_recent_activity(self, limit=20, **kwargs):
        """Return recent activity feed."""
        try:
            data = request.env['consultpro.dashboard'].get_recent_activity(limit=int(limit))
            return {'status': 'ok', 'data': data}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

    @http.route('/consultpro/project/<int:project_id>/health', type='json', auth='user', methods=['POST'])
    def get_project_health(self, project_id, **kwargs):
        """Return health score and risk flags for a specific project."""
        try:
            data = request.env['consultpro.project.service'].get_project_health(project_id)
            return {'status': 'ok', 'data': data}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

    @http.route('/consultpro/project/<int:project_id>/profitability', type='json', auth='user', methods=['POST'])
    def get_project_profitability(self, project_id, **kwargs):
        """Return profitability breakdown for a project."""
        try:
            data = request.env['consultpro.billing.service'].compute_project_profitability(project_id)
            return {'status': 'ok', 'data': data}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}