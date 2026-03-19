# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ConsultProServiceLine(models.Model):
    _name = 'consultpro.service.line'
    _description = 'Contract Service Line'
    _order = 'sequence, id'

    sequence = fields.Integer(default=10)
    contract_id = fields.Many2one(
        'consultpro.contract',
        string='Contract',
        required=True,
        ondelete='cascade',
        index=True,
    )
    service_id = fields.Many2one(
        'consultpro.service',
        string='Service',
        required=True,
        ondelete='restrict',
    )
    description = fields.Text(string='Description')
    billing_type = fields.Selection(
        related='service_id.billing_type',
        string='Billing Type',
        store=True,
    )
    quantity = fields.Float(string='Quantity / Hours', default=1.0, required=True)
    unit_price = fields.Float(string='Unit Price', required=True)
    currency_id = fields.Many2one(
        related='contract_id.currency_id',
        string='Currency',
        store=True,
    )
    discount = fields.Float(string='Discount (%)', default=0.0)
    subtotal = fields.Monetary(
        string='Subtotal',
        compute='_compute_subtotal',
        currency_field='currency_id',
        store=True,
    )
    analytic_account_id = fields.Many2one(
        'account.analytic.account',
        string='Analytic Account',
    )
    is_invoiced = fields.Boolean(string='Invoiced', default=False, readonly=True)

    @api.depends('quantity', 'unit_price', 'discount')
    def _compute_subtotal(self):
        for line in self:
            base = line.quantity * line.unit_price
            line.subtotal = base * (1 - line.discount / 100.0)

    @api.onchange('service_id')
    def _onchange_service_id(self):
        if self.service_id:
            self.unit_price = self.service_id.standard_rate
            self.analytic_account_id = self.service_id.analytic_account_id

    @api.constrains('quantity')
    def _check_quantity(self):
        for rec in self:
            if rec.quantity <= 0:
                raise ValidationError(_("Quantity must be greater than zero."))

    @api.constrains('discount')
    def _check_discount(self):
        for rec in self:
            if not (0 <= rec.discount <= 100):
                raise ValidationError(_("Discount must be between 0% and 100%."))