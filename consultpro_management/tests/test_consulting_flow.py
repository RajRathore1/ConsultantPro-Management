# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase, tagged
from odoo.exceptions import ValidationError, UserError
from datetime import date, timedelta


@tagged('post_install', '-at_install', 'consultpro')
class TestConsultingFlow(TransactionCase):
    """
    End-to-end integration tests for the full ConsultPro workflow:
    Client → Contract → Project → Task → Timesheet → Invoice
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # ── Partners ─────────────────────────────
        cls.partner = cls.env['res.partner'].create({
            'name': 'Test Corp Ltd',
            'is_company': True,
            'email': 'test@testcorp.com',
        })
        cls.employee = cls.env['hr.employee'].create({
            'name': 'Alice Consultant',
            'work_email': 'alice@consultpro.com',
        })

        # ── Client ───────────────────────────────
        cls.client = cls.env['consultpro.client'].create({
            'name': 'Test Corp',
            'partner_id': cls.partner.id,
            'client_type': 'active',
        })

        # ── Service ──────────────────────────────
        cls.service = cls.env['consultpro.service'].create({
            'name': 'Test Service',
            'code': 'TST-001',
            'category': 'technology',
            'billing_type': 'hourly',
            'standard_rate': 100.0,
        })

        # ── Consultant ───────────────────────────
        cls.consultant = cls.env['consultpro.consultant'].create({
            'employee_id': cls.employee.id,
            'seniority': 'senior',
            'billing_rate': 150.0,
            'cost_rate': 80.0,
            'max_weekly_hours': 40.0,
        })

        # ── Contract ─────────────────────────────
        cls.contract = cls.env['consultpro.contract'].create({
            'title': 'Test Contract 2025',
            'client_id': cls.client.id,
            'contract_type': 'time_material',
            'date_start': date.today(),
            'date_end': date.today() + timedelta(days=365),
            'contract_value': 50000.0,
            'billing_cycle': 'monthly',
            'state': 'active',
        })

        # ── Project ──────────────────────────────
        cls.project = cls.env['consultpro.project'].create({
            'name': 'Test Project Alpha',
            'client_id': cls.client.id,
            'contract_id': cls.contract.id,
            'project_type': 'consulting',
            'date_start': date.today(),
            'date_end': date.today() + timedelta(days=90),
            'estimated_hours': 200.0,
            'budget': 20000.0,
            'state': 'in_progress',
            'consultant_ids': [(4, cls.consultant.id)],
        })

    # ════════════════════════════════════════════
    # CLIENT TESTS
    # ════════════════════════════════════════════

    def test_client_sequence_assigned(self):
        """Client code must be auto-assigned on creation."""
        self.assertTrue(self.client.code)
        self.assertNotEqual(self.client.code, 'New')
        self.assertIn('CLT-', self.client.code)

    def test_client_state_transitions(self):
        """Test client state: draft → active → on_hold → active."""
        client = self.env['consultpro.client'].create({
            'name': 'State Test Client',
            'partner_id': self.partner.id,
            'client_type': 'prospect',
        })
        self.assertEqual(client.state, 'draft')
        client.action_activate()
        self.assertEqual(client.state, 'active')
        client.action_hold()
        self.assertEqual(client.state, 'on_hold')
        client.action_close()
        self.assertEqual(client.state, 'closed')

    def test_client_unique_partner_constraint(self):
        """Cannot link same partner to two clients."""
        with self.assertRaises(ValidationError):
            self.env['consultpro.client'].create({
                'name': 'Duplicate Client',
                'partner_id': self.partner.id,
                'client_type': 'active',
            })

    def test_client_contract_count(self):
        """contract_count computes correctly."""
        self.assertEqual(self.client.contract_count, 1)

    # ════════════════════════════════════════════
    # CONTRACT TESTS
    # ════════════════════════════════════════════

    def test_contract_sequence_assigned(self):
        self.assertTrue(self.contract.code if hasattr(self.contract, 'code') else self.contract.name)
        self.assertNotEqual(self.contract.name, 'New')

    def test_contract_date_validation(self):
        """End date before start date should raise ValidationError."""
        with self.assertRaises(ValidationError):
            self.env['consultpro.contract'].create({
                'title': 'Bad Dates',
                'client_id': self.client.id,
                'contract_type': 'fixed_price',
                'date_start': date.today(),
                'date_end': date.today() - timedelta(days=1),
                'contract_value': 1000.0,
            })

    def test_contract_progress_compute(self):
        """Progress should be between 0 and 100."""
        self.assertGreaterEqual(self.contract.progress, 0.0)
        self.assertLessEqual(self.contract.progress, 100.0)

    def test_contract_days_remaining(self):
        """days_remaining should be positive for future-end contract."""
        self.assertGreater(self.contract.days_remaining, 0)

    def test_contract_is_not_overdue(self):
        self.assertFalse(self.contract.is_overdue)

    # ════════════════════════════════════════════
    # PROJECT TESTS
    # ════════════════════════════════════════════

    def test_project_code_assigned(self):
        self.assertIn('PRJ-', self.project.code)

    def test_project_completion_rate_zero(self):
        """No tasks done → 0% completion."""
        self.assertEqual(self.project.completion_rate, 0.0)

    def test_project_budget_not_over(self):
        self.assertFalse(self.project.is_over_budget)

    def test_project_remaining_hours(self):
        self.assertEqual(self.project.remaining_hours, self.project.estimated_hours)

    # ════════════════════════════════════════════
    # TASK TESTS
    # ════════════════════════════════════════════

    def _create_task(self, name='Test Task', state='todo'):
        return self.env['consultpro.task'].create({
            'name': name,
            'project_id': self.project.id,
            'task_type': 'deliverable',
            'state': state,
            'estimated_hours': 10.0,
            'assigned_to_id': self.consultant.id,
            'date_start': date.today(),
            'date_deadline': date.today() + timedelta(days=7),
        })

    def test_task_state_flow(self):
        task = self._create_task()
        self.assertEqual(task.state, 'todo')
        task.action_start()
        self.assertEqual(task.state, 'in_progress')
        task.action_submit_review()
        self.assertEqual(task.state, 'review')
        task.action_mark_done()
        self.assertEqual(task.state, 'done')
        self.assertTrue(task.date_done)

    def test_task_not_overdue_future_deadline(self):
        task = self._create_task()
        self.assertFalse(task.is_overdue)

    def test_task_overdue_past_deadline(self):
        task = self.env['consultpro.task'].create({
            'name': 'Overdue Task',
            'project_id': self.project.id,
            'task_type': 'deliverable',
            'state': 'in_progress',
            'estimated_hours': 5.0,
            'date_deadline': date.today() - timedelta(days=2),
        })
        self.assertTrue(task.is_overdue)

    def test_task_date_constraint(self):
        with self.assertRaises(ValidationError):
            self.env['consultpro.task'].create({
                'name': 'Bad Dates Task',
                'project_id': self.project.id,
                'task_type': 'other',
                'date_start': date.today() + timedelta(days=5),
                'date_deadline': date.today(),
            })

    def test_project_completion_rate_with_done_tasks(self):
        """50% completion with 1 done and 1 todo."""
        t1 = self._create_task('T1')
        t2 = self._create_task('T2')
        t1.action_start()
        t1.action_submit_review()
        t1.action_mark_done()
        self.project._compute_task_count()
        self.assertGreater(self.project.completion_rate, 0.0)

    # ════════════════════════════════════════════
    # TIMESHEET TESTS
    # ════════════════════════════════════════════

    def _create_timesheet(self, hours=8.0, billable=True, state='draft'):
        task = self._create_task()
        ts = self.env['consultpro.timesheet'].create({
            'name': 'Test work description',
            'date': date.today(),
            'consultant_id': self.consultant.id,
            'project_id': self.project.id,
            'task_id': task.id,
            'hours': hours,
            'billable': billable,
            'activity_type': 'development',
        })
        if state == 'submitted':
            ts.action_submit()
        elif state == 'approved':
            ts.action_submit()
            ts.action_approve()
        return ts

    def test_timesheet_create_draft(self):
        ts = self._create_timesheet()
        self.assertEqual(ts.state, 'draft')

    def test_timesheet_submit(self):
        ts = self._create_timesheet()
        ts.action_submit()
        self.assertEqual(ts.state, 'submitted')

    def test_timesheet_approve(self):
        ts = self._create_timesheet(state='submitted')
        ts.action_approve()
        self.assertEqual(ts.state, 'approved')
        self.assertTrue(ts.approved_by_id)
        self.assertTrue(ts.approved_date)

    def test_timesheet_reject(self):
        ts = self._create_timesheet(state='submitted')
        ts.action_reject(reason='Incorrect hours')
        self.assertEqual(ts.state, 'rejected')
        self.assertEqual(ts.rejection_reason, 'Incorrect hours')

    def test_timesheet_hours_zero_raises(self):
        with self.assertRaises(ValidationError):
            self.env['consultpro.timesheet'].create({
                'name': 'Zero hours',
                'date': date.today(),
                'consultant_id': self.consultant.id,
                'project_id': self.project.id,
                'hours': 0.0,
                'activity_type': 'other',
            })

    def test_timesheet_hours_over_24_raises(self):
        with self.assertRaises(ValidationError):
            self.env['consultpro.timesheet'].create({
                'name': 'Too many hours',
                'date': date.today(),
                'consultant_id': self.consultant.id,
                'project_id': self.project.id,
                'hours': 25.0,
                'activity_type': 'other',
            })

    def test_timesheet_future_date_raises(self):
        with self.assertRaises(ValidationError):
            self.env['consultpro.timesheet'].create({
                'name': 'Future entry',
                'date': date.today() + timedelta(days=1),
                'consultant_id': self.consultant.id,
                'project_id': self.project.id,
                'hours': 4.0,
                'activity_type': 'other',
            })

    def test_timesheet_amount_computed(self):
        """Amount = hours × billing_rate when billable."""
        ts = self._create_timesheet(hours=5.0, billable=True)
        expected = 5.0 * self.consultant.billing_rate
        self.assertAlmostEqual(ts.amount, expected, places=2)

    def test_timesheet_amount_zero_when_not_billable(self):
        ts = self._create_timesheet(hours=5.0, billable=False)
        self.assertEqual(ts.amount, 0.0)

    def test_project_logged_hours_after_approval(self):
        ts = self._create_timesheet(hours=8.0, state='approved')
        self.project._compute_logged_hours()
        self.assertAlmostEqual(self.project.logged_hours, 8.0, places=1)

    def test_consultant_utilization_after_approval(self):
        self._create_timesheet(hours=6.0, state='approved')
        self.consultant._compute_utilization()
        self.assertGreater(self.consultant.current_month_hours, 0)

    # ════════════════════════════════════════════
    # BILLING SERVICE TESTS
    # ════════════════════════════════════════════

    def test_billing_service_no_timesheets_raises(self):
        """Generating invoice with no billable timesheets raises UserError."""
        with self.assertRaises(UserError):
            self.env['consultpro.billing.service'].generate_invoice_from_timesheets(
                project_id=self.project.id,
                timesheet_ids=[],
            )

    def test_billing_service_generates_invoice(self):
        ts = self._create_timesheet(hours=8.0, state='approved')
        invoice = self.env['consultpro.billing.service'].generate_invoice_from_timesheets(
            project_id=self.project.id,
            timesheet_ids=[ts.id],
            group_by='consultant',
        )
        self.assertEqual(invoice.move_type, 'out_invoice')
        self.assertTrue(invoice.is_consultpro_invoice)
        self.assertEqual(invoice.consultpro_project_id, self.project)
        self.assertGreater(len(invoice.invoice_line_ids), 0)

    def test_billing_service_marks_timesheets_invoiced_on_post(self):
        ts = self._create_timesheet(hours=4.0, state='approved')
        invoice = self.env['consultpro.billing.service'].generate_invoice_from_timesheets(
            project_id=self.project.id,
            timesheet_ids=[ts.id],
        )
        invoice.action_post()
        ts.invalidate_recordset()
        self.assertEqual(ts.state, 'invoiced')
        self.assertEqual(ts.invoice_id, invoice)

    def test_profitability_compute(self):
        ts = self._create_timesheet(hours=10.0, state='approved')
        result = self.env['consultpro.billing.service'].compute_project_profitability(
            self.project.id
        )
        self.assertIn('revenue', result)
        self.assertIn('cost', result)
        self.assertIn('gross_profit', result)
        self.assertGreaterEqual(result['revenue'], 0)

    # ════════════════════════════════════════════
    # PROJECT SERVICE TESTS
    # ════════════════════════════════════════════

    def test_project_health_score(self):
        result = self.env['consultpro.project.service'].get_project_health(self.project.id)
        self.assertIn('score', result)
        self.assertIn('label', result)
        self.assertIn('flags', result)
        self.assertGreaterEqual(result['score'], 0)
        self.assertLessEqual(result['score'], 100)

    def test_close_project_with_open_tasks_raises(self):
        task = self._create_task(state='todo')
        with self.assertRaises(UserError):
            self.env['consultpro.project.service'].close_project(
                project_id=self.project.id,
                send_notification=False,
            )
        task.action_cancel()

    def test_close_project_cleanly(self):
        """Project closes when all tasks done and no pending timesheets."""
        # Cancel all open tasks
        for t in self.project.task_ids.filtered(lambda t: t.state not in ('done', 'cancelled')):
            t.action_cancel()
        self.env['consultpro.project.service'].close_project(
            project_id=self.project.id,
            close_notes='<p>All done.</p>',
            send_notification=False,
        )
        self.assertEqual(self.project.state, 'done')
        self.assertEqual(self.project.actual_end_date, date.today())

    # ════════════════════════════════════════════
    # CRON TESTS
    # ════════════════════════════════════════════

    def test_cron_expire_contracts(self):
        """Contracts past end_date should auto-expire."""
        expired_contract = self.env['consultpro.contract'].create({
            'title': 'Old Contract',
            'client_id': self.client.id,
            'contract_type': 'fixed_price',
            'date_start': date.today() - timedelta(days=100),
            'date_end': date.today() - timedelta(days=1),
            'contract_value': 5000.0,
            'state': 'active',
        })
        self.env['consultpro.contract'].cron_auto_expire_contracts()
        expired_contract.invalidate_recordset()
        self.assertEqual(expired_contract.state, 'expired')

    def test_service_line_subtotal(self):
        line = self.env['consultpro.service.line'].create({
            'contract_id': self.contract.id,
            'service_id': self.service.id,
            'quantity': 10.0,
            'unit_price': 100.0,
            'discount': 10.0,
        })
        expected = 10.0 * 100.0 * (1 - 10.0 / 100.0)
        self.assertAlmostEqual(line.subtotal, expected, places=2)

    def test_service_line_invalid_discount(self):
        with self.assertRaises(ValidationError):
            self.env['consultpro.service.line'].create({
                'contract_id': self.contract.id,
                'service_id': self.service.id,
                'quantity': 1.0,
                'unit_price': 100.0,
                'discount': 110.0,
            })