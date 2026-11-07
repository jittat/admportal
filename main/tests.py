import shutil
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Banner

# Smallest valid GIF (1x1 pixel), enough for ImageField validation.
TINY_GIF = (b'GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!'
            b'\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00'
            b'\x00\x02\x02D\x01\x00;')

TEMP_MEDIA_ROOT = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=TEMP_MEDIA_ROOT)
class BannerIndexTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA_ROOT, ignore_errors=True)

    def make_banner(self, name, **kwargs):
        return Banner.objects.create(
            image=SimpleUploadedFile(name, TINY_GIF, content_type='image/gif'),
            **kwargs)

    def get_index(self):
        return self.client.get(reverse('main-index'))

    def test_no_banner(self):
        response = self.get_index()
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context['banner'])

    def test_hidden_banner_not_shown(self):
        self.make_banner('hidden.gif', is_hidden=True)
        response = self.get_index()
        self.assertIsNone(response.context['banner'])
        self.assertNotContains(response, 'hidden')

    def test_visible_banner_with_link(self):
        banner = self.make_banner('visible.gif',
                                  link_url='https://example.com/news',
                                  alt_text='ข่าวใหม่')
        self.make_banner('hidden.gif', is_hidden=True)
        response = self.get_index()
        self.assertEqual(response.context['banner'], banner)
        self.assertContains(response, banner.image.url)
        self.assertContains(
            response,
            'href="https://example.com/news" target="_blank" rel="noopener"')
        self.assertContains(response, 'alt="ข่าวใหม่"')

    def test_visible_banner_without_link(self):
        banner = self.make_banner('nolink.gif')
        response = self.get_index()
        self.assertContains(response, banner.image.url)
        self.assertNotContains(response, '<a href=""')

    def test_random_pick_is_always_visible(self):
        visible = {self.make_banner('a.gif').pk, self.make_banner('b.gif').pk}
        self.make_banner('hidden.gif', is_hidden=True)
        for _ in range(10):
            self.assertIn(self.get_index().context['banner'].pk, visible)

    def test_message_and_link_text(self):
        self.make_banner('msg.gif',
                         link_url='https://example.com/news',
                         message='เปิดรับสมัครแล้ว\nรอบที่ 1',
                         link_text='อ่านรายละเอียด')
        response = self.get_index()
        self.assertContains(response, 'เปิดรับสมัครแล้ว<br>รอบที่ 1')
        self.assertContains(
            response,
            '<a class="btn btn-sm btn-success ml-1" '
            'href="https://example.com/news" target="_blank" rel="noopener">'
            'อ่านรายละเอียด</a>',
            html=True)

    def test_message_without_link(self):
        self.make_banner('msg.gif', message='ข้อความ', link_text='ไม่มีลิงก์')
        response = self.get_index()
        self.assertContains(response, 'ข้อความ')
        self.assertNotContains(response, 'ไม่มีลิงก์')

    def test_no_message_paragraph_when_empty(self):
        self.make_banner('plain.gif')
        response = self.get_index()
        self.assertNotContains(response, '<p class="mt-2 mb-0 text-center small">')
