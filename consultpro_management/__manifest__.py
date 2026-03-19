# -*- coding: utf-8 -*-
{
    'name': 'ConsultPro Management',
    'version': '19.0.1.0.0',
    'category': 'Consulting',
    'summary': 'End-to-end Consulting Firm Management: Clients, Contracts, Projects, Timesheets, Invoicing',
    'description': """
        ConsultPro Management
        =====================
        A complete consulting firm management solution for Odoo 19.

        Features:
        ---------
        * Client & Contract Management
        * Service Catalog with Service Lines
        * Project & Task Management (linked to contracts)
        * Timesheet Logging & Approval Workflow
        * Consultant Profiles & Utilization Tracking
        * Automated Invoice Generation
        * KPI Dashboard
        * Client Portal Access
        * Email Notifications & Cron Jobs
    """,
    'author': 'ConsultPro Team',
    'website': 'https://www.consultpro.com',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'mail',
        'portal',
        'project',
        'hr',
        'hr_timesheet',
        'account',
        'sale_management',
        'analytic',
        'web',
    ],
    'data': [
        # Security (always first)
        'security/consultpro_security.xml',
        'security/ir.model.access.csv',

        # Data & Sequences
        'data/consultpro_sequence.xml',
        'data/consultpro_mail_template.xml',
        'data/consultpro_cron.xml',

        # Views — actions pehle define honge, menu sabse aakhir mein
        'views/consultpro_client_views.xml',
        'views/consultpro_contract_views.xml',
        'views/consultpro_service_views.xml',
        'views/consultpro_project_views.xml',
        'views/consultpro_task_views.xml',
        'views/consultpro_timesheet_views.xml',
        'views/consultpro_consultant_views.xml',
        'views/consultpro_invoice_views.xml',
        'views/consultpro_dashboard_views.xml',
        'views/consultpro_menu_views.xml',

        # Reports
        'reports/project_report.xml',
        'reports/invoice_report.xml',
        'reports/consultant_utilization_report.xml',
    ],
    'demo': [
        'data/consultpro_demo_data.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'images': ['static/description/banner.png'],
}