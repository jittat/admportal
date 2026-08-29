import json
import os
import tempfile
from unittest import mock

import requests

from django.test import TestCase
from django.urls import reverse
from django.test import override_settings

from majors.models import Campus, Faculty, AdmissionProject
from .models import MajorCuptCode, CurriculumMajor
from .models import AdmissionCriteria, CurriculumMajorAdmissionCriteria
from .search import simplify_title, find_major_cupt_codes
from .views import prepare_admission_criteria
from . import views
from . import evaluation
from . import embeddings
from .embeddings import FakeProvider
from .embeddings import openrouter
from .embeddings.openrouter import OpenRouterProvider


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


class SharedQuotaTest(SearchTestCase):
    """A criteria can carry its whole quota on one major, zero on its siblings.

    The zero means 'counted with the other major', not 'no seats' — such majors
    must still be listed.
    """

    def setUp(self):
        super().setUp()
        self.project = self.create_project('พัฒนาเครือข่ายองค์กรแห่งการเรียนรู้')
        self.criteria = AdmissionCriteria.objects.create(admission_project=self.project,
                                                         faculty=self.faculty,
                                                         campus=self.campus)
        self.carrier = self.add_major('วท.บ. สาขาวิชาคณิตศาสตร์', '101', slots=36)
        self.shared = self.add_major('วท.บ. สาขาวิชาพฤกษศาสตร์', '102', slots=0)

    def add_major(self, title, program_code, slots):
        code = self.create_code(title, program_code)
        curriculum_major = CurriculumMajor.objects.create(admission_project=self.project,
                                                          cupt_code=code,
                                                          faculty=self.faculty,
                                                          campus=self.campus)
        CurriculumMajorAdmissionCriteria.objects.create(
            curriculum_major=curriculum_major,
            admission_criteria=self.criteria,
            slots=slots)
        return code

    def test_criteria_rows_keep_the_zero_slot_major(self):
        rows, _ = prepare_admission_criteria([self.criteria],
                                             CurriculumMajor.objects.filter(
                                                 admission_project=self.project),
                                             True)

        listed = [mc.curriculum_major.cupt_code for row in rows for mc in row['majors']]
        self.assertIn(self.carrier, listed)
        self.assertIn(self.shared, listed)

    def test_quota_carrying_major_is_listed_first(self):
        # a second criteria whose zero-slot majors are inserted *before* the
        # one carrying the quota, so insertion order alone would bury it
        self.criteria = AdmissionCriteria.objects.create(admission_project=self.project,
                                                         faculty=self.faculty,
                                                         campus=self.campus)
        self.add_major('วท.บ. สาขาวิชาสถิติ', '104', slots=0)
        self.add_major('วท.บ. สาขาวิชาฟิสิกส์', '105', slots=0)
        carrier = self.add_major('วท.บ. สาขาวิชาเคมี', '106', slots=12)

        rows, _ = prepare_admission_criteria([self.criteria],
                                             CurriculumMajor.objects.filter(
                                                 admission_project=self.project),
                                             True)

        listed = [mc for row in rows for mc in row['majors']]
        self.assertEqual([mc.slots for mc in listed], [12, 0, 0])
        self.assertEqual(listed[0].curriculum_major.cupt_code, carrier)

    def test_project_page_shows_the_zero_slot_major(self):
        response = self.client.get(reverse('criteria:project-index',
                                           args=[self.project.id]))

        self.assertContains(response, 'พฤกษศาสตร์')
        self.assertContains(response, 'จำนวนรับรวมกับเงื่อนไขอื่น')

    def test_search_marks_the_zero_slot_major_instead_of_showing_nought(self):
        response = self.client.get(reverse('criteria:search-majors'),
                                   {'query': 'พฤกษศาสตร์'})

        row = response.context['results'][0]['project_rows'][0]
        self.assertEqual(row['slots'], 0)
        self.assertEqual(row['criteria_count'], 1)
        self.assertContains(response, 'จำนวนรับรวมกับเงื่อนไขอื่น')

    def test_search_still_shows_a_dash_when_no_criteria_exist(self):
        project = self.create_project('โครงการที่ยังไม่มีเกณฑ์')
        code = self.create_code('วท.บ. สาขาวิชาสถิติ', '103')
        CurriculumMajor.objects.create(admission_project=project,
                                       cupt_code=code,
                                       faculty=self.faculty,
                                       campus=self.campus)

        response = self.client.get(reverse('criteria:search-majors'),
                                   {'query': 'สถิติ'})

        row = response.context['results'][0]['project_rows'][0]
        self.assertEqual(row['criteria_count'], 0)
        self.assertNotContains(response, 'จำนวนรับรวมกับเงื่อนไขอื่น')


class EvalSetTest(TestCase):
    """Shape checks for the semantic-search eval set (docs/semantic-search.md).

    These do not touch the corpus: the test database is empty, so whether a
    label still names a real major is checked by scripts/eval_baseline.py
    against the live data instead.
    """

    def setUp(self):
        self.eval_set = evaluation.load_eval_set()
        self.queries = self.eval_set['queries']

    def test_loads_and_is_not_empty(self):
        self.assertGreaterEqual(len(self.queries), 30)

    def test_no_duplicate_queries(self):
        texts = [e['query'] for e in self.queries]
        self.assertEqual(len(texts), len(set(texts)))

    def test_every_band_is_declared(self):
        for entry in self.queries:
            self.assertIn(entry['band'], self.eval_set['bands'])

    def test_every_declared_band_is_used(self):
        used = set(e['band'] for e in self.queries)
        self.assertEqual(used, set(self.eval_set['bands']))

    def test_scored_queries_have_labels(self):
        for entry in self.queries:
            if entry['band'] != evaluation.NEGATIVE_BAND:
                self.assertTrue(entry['expected'], entry['query'])

    def test_negative_queries_have_no_labels(self):
        for entry in self.queries:
            if entry['band'] == evaluation.NEGATIVE_BAND:
                self.assertEqual(entry['expected'], [], entry['query'])

    def test_labels_are_unique_within_a_query(self):
        for entry in self.queries:
            self.assertEqual(len(entry['expected']),
                             len(set(entry['expected'])), entry['query'])


class EvalMetricsTest(TestCase):
    def test_recall_normalized_by_k_not_by_label_count(self):
        # seven correct answers cannot all fit in a top-5, so a top-5 holding
        # five of them is a perfect score, not 5/7
        expected = list('abcdefg')
        self.assertEqual(evaluation.recall_at_k(expected, expected, k=5), 1.0)

    def test_recall_counts_only_the_top_k(self):
        self.assertEqual(evaluation.recall_at_k(['x', 'x', 'a'], ['a'], k=2),
                         0.0)

    def test_reciprocal_rank_of_a_miss_is_zero(self):
        self.assertEqual(evaluation.reciprocal_rank(['x'], ['a']), 0.0)

    def test_duplicate_titles_collapse_before_scoring(self):
        # a title on several rows must not consume several top-5 slots
        entry = {'query': 'q', 'band': 'field_level', 'expected': ['b']}
        ranked = ['a', 'a', 'a', 'a', 'a', 'b']
        self.assertEqual(evaluation.score_query(entry, ranked)['recall_at_k'],
                         1.0)

    def test_negative_band_is_scored_on_false_positives(self):
        entry = {'query': 'q', 'band': 'negative', 'expected': []}
        scored = evaluation.score_query(entry, ['a', 'b'])
        self.assertEqual(scored['false_positives'], 2)
        self.assertNotIn('recall_at_k', scored)

    def test_negative_band_excluded_from_overall(self):
        eval_set = {'queries': [
            {'query': 'a', 'band': 'near_exact', 'expected': ['A']},
            {'query': 'b', 'band': 'negative', 'expected': []},
        ]}
        report = evaluation.evaluate(lambda q: ['A'], eval_set)
        self.assertEqual(report['overall']['n'], 1)
        self.assertEqual(report['overall']['recall_at_k'], 1.0)
        self.assertEqual(report['bands']['negative']['false_positives'], 1.0)


class FakeProviderTest(TestCase):
    def test_is_deterministic(self):
        a, b = FakeProvider(dimensions=16), FakeProvider(dimensions=16)
        self.assertEqual(a.embed_query('หมอ'), b.embed_query('หมอ'))

    def test_different_texts_differ(self):
        p = FakeProvider(dimensions=16)
        self.assertNotEqual(p.embed_query('หมอ'), p.embed_query('ครู'))

    def test_vectors_are_unit_length(self):
        p = FakeProvider(dimensions=16)
        length = sum(x * x for x in p.embed_query('หมอ'))
        self.assertAlmostEqual(length, 1.0)

    def test_pinned_vectors_win(self):
        p = FakeProvider(dimensions=2, vectors={'ก': [1.0, 0.0]})
        self.assertEqual(p.embed_query('ก'), [1.0, 0.0])
        self.assertEqual(len(p.embed_query('ข')), 2)

    def test_embed_documents_preserves_order(self):
        p = FakeProvider(dimensions=8)
        texts = ['ก', 'ข', 'ค']
        self.assertEqual(p.embed_documents(texts),
                         [p.embed_query(t) for t in texts])


class VectorMathTest(TestCase):
    def test_cosine_rejects_mismatched_lengths(self):
        with self.assertRaises(ValueError):
            embeddings.cosine([1.0], [1.0, 0.0])

    def test_cosine_of_zero_vector_is_zero_not_an_error(self):
        self.assertEqual(embeddings.cosine([0.0, 0.0], [1.0, 0.0]), 0.0)

    def test_ranks_most_similar_first(self):
        corpus = [('far', [0.0, 1.0]), ('near', [1.0, 0.0])]
        ranked = embeddings.rank_by_similarity([1.0, 0.0], corpus)
        self.assertEqual([label for label, _ in ranked], ['near', 'far'])

    def test_ties_keep_corpus_order(self):
        corpus = [('a', [1.0, 0.0]), ('b', [1.0, 0.0])]
        ranked = embeddings.rank_by_similarity([1.0, 0.0], corpus)
        self.assertEqual([label for label, _ in ranked], ['a', 'b'])

    def test_floor_excludes_an_unrelated_vector(self):
        corpus = [('related', [1.0, 0.0]), ('unrelated', [-1.0, 0.0])]
        ranked = embeddings.rank_by_similarity([1.0, 0.0], corpus, floor=0.5)
        self.assertEqual([label for label, _ in ranked], ['related'])

    def test_limit_caps_the_ranking(self):
        corpus = [('a', [1.0, 0.0]), ('b', [0.9, 0.1]), ('c', [0.8, 0.2])]
        ranked = embeddings.rank_by_similarity([1.0, 0.0], corpus, limit=2)
        self.assertEqual(len(ranked), 2)


class StubResponse:
    """Enough of a requests.Response for the adapter: status, json(), text."""

    def __init__(self, status_code=200, payload=None, text=None, headers=None):
        self.status_code = status_code
        self._payload = payload
        self.text = text if text is not None else json.dumps(payload)
        self.headers = headers or {}

    def json(self):
        if self._payload is None:
            raise ValueError('no JSON object could be decoded')
        return self._payload


class StubSession:
    """A requests.Session stand-in that replays a queued list of outcomes.

    An entry that is an exception is raised, so connection failures and rate
    limits are expressed the same way the real session expresses them.
    """

    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = []

    def post(self, url, json=None, headers=None, timeout=None):
        self.calls.append({'url': url, 'json': json, 'headers': headers,
                           'timeout': timeout})
        outcome = (self.outcomes.pop(0) if self.outcomes
                   else self.outcomes_exhausted())
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    def outcomes_exhausted(self):
        raise AssertionError('the adapter made more requests than expected')


def _embedding_payload(count, dimensions=3, reverse=False):
    data = [{'index': i, 'embedding': [float(i)] * dimensions}
            for i in range(count)]
    if reverse:
        data.reverse()
    return {'data': data, 'model': 'test', 'usage': {'total_tokens': 1}}


def _ok(count, dimensions=3, reverse=False):
    return StubResponse(200, _embedding_payload(count, dimensions, reverse))


class OpenRouterProviderTest(TestCase):
    """No test here touches the network: every provider gets a StubSession."""

    def provider(self, outcomes=(), **kwargs):
        kwargs.setdefault('api_key', 'test-key')
        kwargs.setdefault('sleep', lambda seconds: None)
        session = StubSession(outcomes)
        provider = OpenRouterProvider(session=session, **kwargs)
        provider.stub = session
        return provider

    def test_empty_input_makes_no_request(self):
        provider = self.provider()
        self.assertEqual(provider.embed_documents([]), [])
        self.assertEqual(provider.stub.calls, [])

    def test_batches_long_input(self):
        provider = self.provider([_ok(2), _ok(2), _ok(1)], batch_size=2)
        vectors = provider.embed_documents(['a', 'b', 'c', 'd', 'e'])
        self.assertEqual(len(vectors), 5)
        self.assertEqual(len(provider.stub.calls), 3)
        self.assertEqual(provider.stub.calls[0]['json']['input'], ['a', 'b'])
        self.assertEqual(provider.stub.calls[2]['json']['input'], ['e'])

    def test_orders_by_index_not_by_array_position(self):
        # a provider is free to return the array in any order; the index is
        # what pairs a vector with its text, and mispairing 290 majors would
        # be silent
        provider = self.provider([_ok(3, reverse=True)])
        self.assertEqual(provider.embed_documents(['a', 'b', 'c']),
                         [[0.0] * 3, [1.0] * 3, [2.0] * 3])

    def test_short_response_is_an_error(self):
        provider = self.provider([_ok(2)])
        with self.assertRaises(embeddings.EmbeddingError):
            provider.embed_documents(['a', 'b', 'c'])

    def test_retries_a_rate_limit_then_succeeds(self):
        provider = self.provider([StubResponse(429, text='slow down'), _ok(1)])
        self.assertEqual(len(provider.embed_documents(['a'])), 1)
        self.assertEqual(len(provider.stub.calls), 2)

    def test_honours_retry_after_within_a_cap(self):
        waits = []
        provider = self.provider(
            [StubResponse(429, text='slow down', headers={'Retry-After': '4'}),
             _ok(1)],
            sleep=waits.append)
        provider.embed_documents(['a'])
        self.assertEqual(waits, [4.0])

    def test_caps_an_unreasonable_retry_after(self):
        waits = []
        provider = self.provider(
            [StubResponse(429, text='later',
                          headers={'Retry-After': '3600'}), _ok(1)],
            sleep=waits.append)
        provider.embed_documents(['a'])
        self.assertEqual(waits, [openrouter.MAX_RETRY_AFTER])

    def test_retries_a_connection_failure(self):
        provider = self.provider([requests.ConnectionError('down'), _ok(1)])
        self.assertEqual(len(provider.embed_documents(['a'])), 1)

    def test_does_not_retry_a_bad_request(self):
        provider = self.provider([StubResponse(400, text='bad model')])
        with self.assertRaises(embeddings.EmbeddingError):
            provider.embed_documents(['a'])
        self.assertEqual(len(provider.stub.calls), 1)

    def test_gives_up_after_max_attempts(self):
        provider = self.provider([requests.ConnectionError('down')]
                                 * openrouter.MAX_ATTEMPTS)
        with self.assertRaises(embeddings.EmbeddingError):
            provider.embed_documents(['a'])
        self.assertEqual(len(provider.stub.calls), openrouter.MAX_ATTEMPTS)

    def test_a_timeout_is_an_embedding_error_not_a_crash(self):
        # Phase 4 degrades on this rather than 500ing the search page
        provider = self.provider([requests.Timeout('too slow')]
                                 * openrouter.MAX_ATTEMPTS)
        with self.assertRaises(embeddings.EmbeddingError):
            provider.embed_documents(['a'])

    def test_unparseable_json_is_an_embedding_error(self):
        provider = self.provider([StubResponse(200, None, text='<html>502')])
        with self.assertRaises(embeddings.EmbeddingError):
            provider.embed_documents(['a'])

    def test_the_timeout_is_passed_to_the_session(self):
        provider = self.provider([_ok(1)], timeout=1.5)
        provider.embed_documents(['a'])
        self.assertEqual(provider.stub.calls[0]['timeout'], 1.5)

    def test_the_key_is_sent_as_a_bearer_token(self):
        provider = self.provider([_ok(1)])
        provider.embed_documents(['a'])
        self.assertEqual(provider.stub.calls[0]['headers']['Authorization'],
                         'Bearer test-key')

    def test_payload_denies_data_collection_by_default(self):
        payload = self.provider()._payload(['a'])
        self.assertEqual(payload['provider'], {'data_collection': 'deny'})

    def test_data_collection_can_be_allowed_deliberately(self):
        payload = self.provider(deny_data_collection=False)._payload(['a'])
        self.assertNotIn('provider', payload)

    def test_dimensions_are_sent_only_when_asked_for(self):
        self.assertNotIn('dimensions', self.provider()._payload(['a']))
        self.assertEqual(self.provider(dimensions=256)._payload(['a'])
                         ['dimensions'], 256)

    def test_dimensions_are_learnt_from_the_first_response(self):
        provider = self.provider([_ok(1, dimensions=7)])
        provider.embed_documents(['a'])
        self.assertEqual(provider.dimensions, 7)

    def test_reuses_one_session(self):
        provider = OpenRouterProvider(api_key='k')
        self.assertIsInstance(provider.session, requests.Session)

    def test_a_real_json_decode_error_is_not_retried(self):
        # requests.JSONDecodeError subclasses both ValueError and
        # RequestException; if it reached the retry handler an HTML error page
        # would be retried as though it were a connection failure
        response = requests.Response()
        response.status_code = 200
        response._content = b'<html>502 Bad Gateway</html>'
        response.encoding = 'utf-8'
        provider = self.provider([response])
        with self.assertRaises(embeddings.EmbeddingError):
            provider.embed_documents(['a'])
        self.assertEqual(len(provider.stub.calls), 1)


class ApiKeyTest(TestCase):
    def test_environment_wins(self):
        with mock.patch.dict(os.environ, {openrouter.ENV_VAR: 'from-env'}):
            self.assertEqual(openrouter.read_api_key(), 'from-env')

    def test_falls_back_to_dotenv(self):
        with tempfile.NamedTemporaryFile('w', suffix='.env', delete=False,
                                         encoding='utf-8') as f:
            f.write('# a comment\n%s="from-file"\nOTHER=x\n'
                    % openrouter.ENV_VAR)
            path = f.name
        self.addCleanup(os.unlink, path)
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(openrouter.read_api_key(path), 'from-file')

    def test_missing_key_names_the_variable(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(embeddings.EmbeddingError) as caught:
                openrouter.read_api_key('/nonexistent/.env')
        self.assertIn(openrouter.ENV_VAR, str(caught.exception))

    def test_missing_dotenv_is_not_an_error(self):
        self.assertEqual(openrouter.read_env_file('/nonexistent/.env'), {})


class VectorIndexTest(TestCase):
    def test_reports_its_shape(self):
        index = embeddings.VectorIndex(['a', 'b'], [[1.0, 0.0], [0.0, 1.0]])
        self.assertEqual(len(index), 2)
        self.assertEqual(index.dimensions, 2)

    def test_empty_corpus_searches_to_nothing(self):
        self.assertEqual(embeddings.VectorIndex([], []).search([1.0]), [])

    def test_mismatched_labels_and_vectors_are_rejected(self):
        with self.assertRaises(ValueError):
            embeddings.VectorIndex(['a'], [[1.0], [2.0]])

    def test_query_of_the_wrong_width_is_rejected(self):
        index = embeddings.VectorIndex(['a'], [[1.0, 0.0]])
        with self.assertRaises(ValueError):
            index.search([1.0, 0.0, 0.0])

    def test_unnormalized_vectors_still_rank_by_angle(self):
        # magnitude must not decide the ranking; only direction
        index = embeddings.VectorIndex(['long', 'aligned'],
                                       [[0.0, 90.0], [0.5, 0.0]])
        ranked = index.search([1.0, 0.0])
        self.assertEqual(ranked[0][0], 'aligned')
        self.assertAlmostEqual(ranked[0][1], 1.0, places=5)

    def test_a_zero_vector_does_not_poison_the_ranking(self):
        index = embeddings.VectorIndex(['zero', 'real'],
                                       [[0.0, 0.0], [1.0, 0.0]])
        ranked = index.search([1.0, 0.0])
        self.assertEqual(ranked[0][0], 'real')
        self.assertFalse(any(score != score for _, score in ranked))  # no nan

    def test_scores_are_plain_floats(self):
        # they end up in JSON and in %-formatting, so numpy scalars would leak
        index = embeddings.VectorIndex(['a'], [[1.0, 0.0]])
        self.assertIs(type(index.search([1.0, 0.0])[0][1]), float)

    def test_matches_the_pure_python_cosine(self):
        vectors = [[0.3, 0.9, 0.1], [0.8, 0.1, 0.5], [0.2, 0.2, 0.7]]
        index = embeddings.VectorIndex(['a', 'b', 'c'], vectors)
        query = [0.5, 0.4, 0.3]
        for label, score in index.search(query):
            expected = embeddings.cosine(query, vectors['abc'.index(label)])
            self.assertAlmostEqual(score, expected, places=5)
