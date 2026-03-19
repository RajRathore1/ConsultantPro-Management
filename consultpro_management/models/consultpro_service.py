# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ConsultProService(models.Model):
    _name = 'consultpro.service'
    _description = 'ConsultPro Service Catalog'
    _inherit = ['mail.thread']
    _rec_name = 'name'
    _order = 'sequence, name'

    name = fields.Char(string='Service Name', required=True, tracking=True, index=True)
    code = fields.Char(string='Service Code', required=True, copy=False, index=True)
    sequence = fields.Integer(string='Sequence', default=10)
    active = fields.Boolean(default=True)

    category = fields.Selection([
        ('strategy', 'Strategy Consulting'),
        ('technology', 'Technology Consulting'),
        ('finance', 'Finance & Accounting'),
        ('hr', 'HR & Organizational'),
        ('operations', 'Operations'),
        ('marketing', 'Marketing & Sales'),
        ('legal', 'Legal & Compliance'),
        ('other', 'Other'),
    ], string='Category', required=True, default='other')

    description = fields.Html(string='Service Description')
    deliverables = fields.Text(string='Expected Deliverables')

    # ─────────────────────────────────────────────
    # Pricing
    # ─────────────────────────────────────────────
    billing_type = fields.Selection([
        ('hourly', 'Hourly Rate'),
        ('daily', 'Daily Rate'),
        ('fixed', 'Fixed Price'),
        ('monthly', 'Monthly Retainer'),
    ], string='Default Billing Type', default='hourly', required=True)

    standard_rate = fields.Float(string='Standard Rate', digits=(16, 2))
    currency_id = fields.Many2one(
        'res.currency',
        default=lambda self: self.env.company.currency_id,
    )

    # ─────────────────────────────────────────────
    # Skill Tags
    # ─────────────────────────────────────────────
    skill_tag_ids = fields.Many2many(
        'hr.skill',
        'service_skill_rel',
        'service_id', 'skill_id',
        string='Required Skills',
    )

    # ─────────────────────────────────────────────
    # Analytics
    # ─────────────────────────────────────────────
    analytic_account_id = fields.Many2one(
        'account.analytic.account',
        string='Analytic Account',
    )
    product_id = fields.Many2one(
        'product.product',
        string='Related Product',
        domain=[('type', '=', 'service')],
    )

    # ─────────────────────────────────────────────
    # Stats
    # ─────────────────────────────────────────────
    service_line_count = fields.Integer(
        string='Used in Contracts',
        compute='_compute_service_line_count',
    )

    @api.depends()
    def _compute_service_line_count(self):
        ServiceLine = self.env['consultpro.service.line']
        for rec in self:
            rec.service_line_count = ServiceLine.search_count(
                [('service_id', '=', rec.id)]
            )

    @api.constrains('code')
    def _check_unique_code(self):
        for rec in self:
            if self.search_count([('code', '=', rec.code), ('id', '!=', rec.id)]) > 0:
                raise ValidationError(_("Service code '%s' already exists.") % rec.code)