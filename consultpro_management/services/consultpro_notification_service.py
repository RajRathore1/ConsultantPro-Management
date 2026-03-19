# -*- coding: utf-8 -*-
from odoo import models, api, _


class ConsultProNotificationService(models.AbstractModel):
    _name = 'consultpro.notification.service'
    _description = 'ConsultPro Notification & Email Service'

    def _get_template(self, xml_id):
        return self.env.ref(
            f'consultpro_management.{xml_id}', raise_if_not_found=False
        )

    def notify_project_closed(self, project):
        template = self._get_template('mail_template_project_closed')
        if template:
            template.send_mail(project.id, force_send=True)

    def notify_contract_expiring(self, contract):
        template = self._get_template('mail_template_contract_expiring')
        if template:
            template.send_mail(contract.id, force_send=True)

    def notify_invoice_generated(self, invoice):
        template = self._get_template('mail_template_invoice_generated')
        if template:
            template.send_mail(invoice.id, force_send=True)

    def notify_timesheet_approved(self, timesheet):
        template = self._get_template('mail_template_timesheet_approved')
        if template:
            template.send_mail(timesheet.id, force_send=True)

    def notify_timesheet_rejected(self, timesheet):
        template = self._get_template('mail_template_timesheet_rejected')
        if template:
            template.send_mail(timesheet.id, force_send=True)

    @api.model
    def cron_notify_expiring_contracts(self):
        """Cron: notify managers of contracts expiring in 30 or 7 days."""
        from datetime import timedelta
        today = fields.Date.today()  # noqa — imported from context
        from odoo import fields as odoo_fields
        today = odoo_fields.Date.today()
        warn_dates = [today + timedelta(days=d) for d in (30, 7)]
        for warn_date in warn_dates:
            expiring = self.env['consultpro.contract'].search([
                ('state', '=', 'active'),
                ('date_end', '=', str(warn_date)),
            ])
            for contract in expiring:
                self.notify_contract_expiring(contract)
                contract.message_post(
                    body=_("Contract expires on %s. Renewal reminder sent.") % str(contract.date_end),
                )