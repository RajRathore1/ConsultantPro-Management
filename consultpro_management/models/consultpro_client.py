# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ConsultProClient(models.Model):
    _name = 'consultpro.client'
    _description = 'ConsultPro Client'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'
    _order = 'name asc'

    # ─────────────────────────────────────────────
    # Basic Info
    # ─────────────────────────────────────────────
    name = fields.Char(
        string='Client Name',
        required=True,
        tracking=True,
        index=True,
    )
    code = fields.Char(
        string='Client Code',
        readonly=True,
        copy=False,
        default='New',
        index=True,
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Related Partner',
        required=True,
        tracking=True,
        domain=[('is_company', '=', True)],
        ondelete='restrict',
    )
    industry_id = fields.Many2one(
        'res.partner.industry',
        string='Industry',
        tracking=True,
    )
    client_type = fields.Selection([
        ('prospect', 'Prospect'),
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('vip', 'VIP'),
    ], string='Client Type', default='prospect', tracking=True, required=True)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('on_hold', 'On Hold'),
        ('closed', 'Closed'),
    ], string='Status', default='draft', tracking=True, required=True)

    # ─────────────────────────────────────────────
    # Contact Info
    # ─────────────────────────────────────────────
    primary_contact_id = fields.Many2one(
        'res.partner',
        string='Primary Contact',
        domain="[('parent_id', '=', partner_id)]",
    )
    email = fields.Char(related='partner_id.email', string='Email', store=True)
    phone = fields.Char(related='partner_id.phone', string='Phone', store=True)
    website = fields.Char(related='partner_id.website', string='Website', store=True)
    country_id = fields.Many2one(related='partner_id.country_id', string='Country', store=True)

    # ─────────────────────────────────────────────
    # Internal
    # ─────────────────────────────────────────────
    account_manager_id = fields.Many2one(
        'res.users',
        string='Account Manager',
        default=lambda self: self.env.user,
        tracking=True,
    )
    date_onboarded = fields.Date(string='Onboarding Date', tracking=True)
    notes = fields.Html(string='Internal Notes')
    rating = fields.Selection([
        ('1', '★'),
        ('2', '★★'),
        ('3', '★★★'),
        ('4', '★★★★'),
        ('5', '★★★★★'),
    ], string='Client Rating', default='3')

    # ─────────────────────────────────────────────
    # Relational
    # ─────────────────────────────────────────────
    contract_ids = fields.One2many(
        'consultpro.contract', 'client_id',
        string='Contracts',
    )
    contract_count = fields.Integer(
        string='Contract Count',
        compute='_compute_contract_count',
        store=True,
    )
    project_ids = fields.One2many(
        'consultpro.project', 'client_id',
        string='Projects',
    )
    project_count = fields.Integer(
        string='Project Count',
        compute='_compute_project_count',
        store=True,
    )
    invoice_ids = fields.One2many(
        'account.move', 'partner_id',
        string='Invoices',
        domain=[('move_type', '=', 'out_invoice')],
    )
    total_revenue = fields.Monetary(
        string='Total Revenue',
        compute='_compute_total_revenue',
        currency_field='currency_id',
        store=True,
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id,
    )

    # ─────────────────────────────────────────────
    # Computes
    # ─────────────────────────────────────────────
    @api.depends('contract_ids')
    def _compute_contract_count(self):
        for rec in self:
            rec.contract_count = len(rec.contract_ids)

    @api.depends('project_ids')
    def _compute_project_count(self):
        for rec in self:
            rec.project_count = len(rec.project_ids)

    @api.depends('invoice_ids.amount_total', 'invoice_ids.state')
    def _compute_total_revenue(self):
        for rec in self:
            paid_invoices = rec.invoice_ids.filtered(
                lambda i: i.state == 'posted' and i.payment_state == 'paid'
            )
            rec.total_revenue = sum(paid_invoices.mapped('amount_total'))

    # ─────────────────────────────────────────────
    # ORM Overrides
    # ─────────────────────────────────────────────
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('code', 'New') == 'New':
                vals['code'] = self.env['ir.sequence'].next_by_code(
                    'consultpro.client'
                ) or 'CLT-0001'
        return super().create(vals_list)

    def name_get(self):
        return [(rec.id, f"[{rec.code}] {rec.name}") for rec in self]

    # ─────────────────────────────────────────────
    # Constraints
    # ─────────────────────────────────────────────
    @api.constrains('partner_id')
    def _check_unique_partner(self):
        for rec in self:
            existing = self.search([
                ('partner_id', '=', rec.partner_id.id),
                ('id', '!=', rec.id),
            ])
            if existing:
                raise ValidationError(_(
                    "Partner '%s' is already linked to client '%s'."
                ) % (rec.partner_id.name, existing[0].name))

    # ─────────────────────────────────────────────
    # Actions
    # ─────────────────────────────────────────────
    def action_activate(self):
        self.write({'state': 'active'})

    def action_hold(self):
        self.write({'state': 'on_hold'})

    def action_close(self):
        self.write({'state': 'closed'})

    def action_view_contracts(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Contracts'),
            'res_model': 'consultpro.contract',
            'view_mode': 'list,form',
            'domain': [('client_id', '=', self.id)],
            'context': {'default_client_id': self.id},
        }

    def action_view_projects(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Projects'),
            'res_model': 'consultpro.project',
            'view_mode': 'list,kanban,form',
            'domain': [('client_id', '=', self.id)],
            'context': {'default_client_id': self.id},
        }