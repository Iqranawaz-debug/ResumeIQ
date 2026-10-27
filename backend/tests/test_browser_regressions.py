"""Synthetic defects reproduced by the Phase 5.1 real-browser journeys."""
from network_guard import OfflineTestCase
from extractor.employment import employment, projects


class BrowserExtractionRegressions(OfflineTestCase):
    def test_first_person_activity_is_not_an_employer(self):
        entries = employment(['Software Developer | Example Labs', 'Jan 2020 - Dec 2021',
                              'Utilized Python for reports.', 'I maintained FastAPI services.'])
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]['organization'], 'Example Labs')
        self.assertIn('I maintained FastAPI services.', entries[0]['details'])

    def test_standalone_project_dates_belong_to_current_project(self):
        entries = projects(['Portfolio Dashboard', 'Jan 2024 - Dec 2024',
                            'Utilized React for charts.', 'Research Tool', 'Built a Python demonstration.'])
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0]['title'], 'Portfolio Dashboard')
        self.assertEqual(entries[0]['details'], ['Jan 2024 - Dec 2024', 'Utilized React for charts.'])
        self.assertEqual(entries[1]['title'], 'Research Tool')

    def test_real_organization_with_services_remains_header(self):
        entries = employment(['Software Developer', 'Example Services Ltd.', 'Jan 2020 - Dec 2021',
                              'Maintained internal services.'])
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]['organization'], 'Example Services Ltd.')
        self.assertEqual(entries[0]['details'], ['Maintained internal services.'])
