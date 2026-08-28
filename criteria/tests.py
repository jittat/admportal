from django.test import TestCase
from django.urls import reverse
from django.test import override_settings

from majors.models import Campus, Faculty, AdmissionProject
from .models import MajorCuptCode, CurriculumMajor
from .models import AdmissionCriteria, CurriculumMajorAdmissionCriteria
from .search import simplify_title, find_major_cupt_codes
from . import views


class SimplifyTitleTest(TestCase):
    def test_removes_spaces_parens_and_thanthakhat(self):
        self.assertEqual(simplify_title('วศ.บ. สาขาวิชาวิศวกรรมเคมี (ภาษาไทย ปกติ)'),
                         'วศ.บ.สาขาวิชาวิศวกรรมเคมีภาษาไทยปกติ')

    def test_empty(self):
        self.assertEqual(simplify_title('   '), '')


class SearchTestCase(TestCase):
    def setUp(self):
        self.campus = Campus.objects.create(title='บางเขน', short_title='บางเขน')
        self.faculty = Faculty.objects.create(title='คณะวิศวกรรมศาสตร์',
                                              campus=self.campus)

    def create_code(self, title, program_code, major_code=''):
        return MajorCuptCode.objects.create(program_code=program_code,
                                            program_type='ภาษาไทย ปกติ',
                                            program_type_code='A',
                                            major_code=major_code,
                                            faculty=self.faculty,
                                            campus=self.campus,
                                            title=title)

    def create_project(self, title, major_detail_visible=True, round_number=1):
        return AdmissionProject.objects.create(title=title,
                                               short_title=title,
                                               campus=self.campus,
                                               major_detail_visible=major_detail_visible,
                                               is_available=True,
                                               default_round_number=round_number)

    def create_curriculum_major(self, code, project, slots=None):
        curriculum_major = CurriculumMajor.objects.create(admission_project=project,
                                                          cupt_code=code,
                                                          faculty=self.faculty,
                                                          campus=self.campus)
        if slots is not None:
            criteria = AdmissionCriteria.objects.create(admission_project=project,
                                                        faculty=self.faculty,
                                                        campus=self.campus)
            CurriculumMajorAdmissionCriteria.objects.create(
                curriculum_major=curriculum_major,
                admission_criteria=criteria,
                slots=slots)
        return curriculum_major


class FindMajorCuptCodesTest(SearchTestCase):
    def setUp(self):
        super().setUp()
        self.computer = self.create_code('วศ.บ. สาขาวิชาวิศวกรรมคอมพิวเตอร์', '001')
        self.chemical = self.create_code('วศ.บ. สาขาวิชาวิศวกรรมเคมี', '002')

    def test_exact_substring(self):
        self.assertEqual(find_major_cupt_codes('วิศวกรรมเคมี'), [self.chemical])

    def test_normalized_match_ignores_thanthakhat_and_spaces(self):
        # the stored title has the thanthakhat that the query omits
        self.assertEqual(find_major_cupt_codes('วิศวกรรมคอมพิวเตอร'),
                         [self.computer])

    def test_all_terms_must_match(self):
        self.assertEqual(find_major_cupt_codes('วิศวกรรม เคมี'), [self.chemical])
        self.assertEqual(find_major_cupt_codes('วิศวกรรม ไฟฟ้า'), [])

    def test_blank_query_matches_nothing(self):
        self.assertEqual(find_major_cupt_codes('   '), [])

    def test_no_match(self):
        self.assertEqual(find_major_cupt_codes('สถาปัตยกรรม'), [])


class SearchViewTest(SearchTestCase):
    def setUp(self):
        super().setUp()
        self.code = self.create_code('วศ.บ. สาขาวิชาวิศวกรรมคอมพิวเตอร์', '001')
        self.url = reverse('criteria:search-majors')

    def test_blank_query_shows_the_form_only(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['has_query'])

    @override_settings(ALLOW_SEARCH=False)
    def test_redirects_when_search_is_disabled(self):
        response = self.client.get(self.url, {'query': 'วิศวกรรม'})
        self.assertRedirects(response, reverse('main-index'))

    def test_forbidden_when_criteria_are_hidden(self):
        views.HIDE_CRITERIA = True
        try:
            response = self.client.get(self.url, {'query': 'วิศวกรรม'})
            self.assertEqual(response.status_code, 403)
        finally:
            views.HIDE_CRITERIA = False

    def test_finds_major_in_a_visible_project(self):
        project = self.create_project('ช้างเผือก')
        self.create_curriculum_major(self.code, project, slots=20)

        response = self.client.get(self.url, {'query': 'วิศวกรรมคอมพิวเตอร์'})

        results = response.context['results']
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['major_cupt_code'], self.code)
        self.assertEqual(len(results[0]['project_rows']), 1)
        self.assertEqual(results[0]['project_rows'][0]['slots'], 20)

    def test_excludes_majors_only_in_hidden_projects(self):
        hidden = self.create_project('โครงการที่ยังไม่เปิด',
                                     major_detail_visible=False)
        self.create_curriculum_major(self.code, hidden, slots=20)

        response = self.client.get(self.url, {'query': 'วิศวกรรมคอมพิวเตอร์'})

        self.assertEqual(response.context['results'], [])

    def test_sums_slots_over_several_criteria(self):
        project = self.create_project('ช้างเผือก')
        curriculum_major = self.create_curriculum_major(self.code, project, slots=5)
        second = AdmissionCriteria.objects.create(admission_project=project,
                                                  faculty=self.faculty,
                                                  campus=self.campus)
        CurriculumMajorAdmissionCriteria.objects.create(
            curriculum_major=curriculum_major,
            admission_criteria=second,
            slots=5)

        response = self.client.get(self.url, {'query': 'วิศวกรรมคอมพิวเตอร์'})

        row = response.context['results'][0]['project_rows'][0]
        self.assertEqual(row['slots'], 10)
        self.assertEqual(row['criteria_count'], 2)

    def test_ignores_deleted_criteria_slots(self):
        project = self.create_project('ช้างเผือก')
        curriculum_major = self.create_curriculum_major(self.code, project, slots=5)
        deleted = AdmissionCriteria.objects.create(admission_project=project,
                                                   faculty=self.faculty,
                                                   campus=self.campus,
                                                   is_deleted=True)
        CurriculumMajorAdmissionCriteria.objects.create(
            curriculum_major=curriculum_major,
            admission_criteria=deleted,
            slots=100)

        response = self.client.get(self.url, {'query': 'วิศวกรรมคอมพิวเตอร์'})

        row = response.context['results'][0]['project_rows'][0]
        self.assertEqual(row['slots'], 5)
        self.assertEqual(row['criteria_count'], 1)

    def test_orders_project_rows_by_round(self):
        round3 = self.create_project('Admission', round_number=3)
        round1 = self.create_project('ช้างเผือก', round_number=1)
        self.create_curriculum_major(self.code, round3, slots=35)
        self.create_curriculum_major(self.code, round1, slots=20)

        response = self.client.get(self.url, {'query': 'วิศวกรรมคอมพิวเตอร์'})

        rows = response.context['results'][0]['project_rows']
        self.assertEqual([r['round_number'] for r in rows], [1, 3])
