from django.db import models

class Announcement(models.Model):
    DEFAULT_ROUND_NUMBER = 2
    
    body = models.TextField()
    more_link_text = models.CharField(max_length=100,
                                      blank=True,
                                      verbose_name='ข้อความบนลิงก์')
    more_link_url = models.CharField(max_length=100,
                                     blank=True,
                                     verbose_name='ลิงก์อ่านต่อ')
    attachment = models.FileField(blank=True,
                                  upload_to='announcements/%Y/%m/%d/',
                                  verbose_name='ไฟล์สำหรับดาวน์โหลด')

    is_published = models.BooleanField(verbose_name='แสดงผลหรือไม่',
                                       default=True)
    created_date = models.DateTimeField(verbose_name='วันเวลาที่ประกาศ')

    admission_round = models.ForeignKey('majors.AdmissionRound',
                                        on_delete=models.CASCADE,
                                        null=True,
                                        blank=True,
                                        default=None)

    rank = models.IntegerField(verbose_name='ลำดับในการแสดง',
                               default=1000)
    has_extra_indent = models.BooleanField(verbose_name='ย่อหน้าเพิ่มเติมหรือไม่',
                                           default=False)
    
    class Meta:
        ordering = ['rank','-created_date']
    
    def __str__(self):
        return self.body


class Banner(models.Model):
    image = models.ImageField(upload_to='banners/%Y/%m/%d/',
                              verbose_name='ภาพแบนเนอร์')
    link_url = models.CharField(max_length=300,
                                blank=True,
                                verbose_name='ลิงก์เมื่อคลิก')
    alt_text = models.CharField(max_length=200,
                                blank=True,
                                verbose_name='คำอธิบายภาพ')
    message = models.TextField(blank=True,
                               verbose_name='ข้อความใต้แบนเนอร์')
    link_text = models.CharField(max_length=200,
                                 blank=True,
                                 verbose_name='ข้อความลิงก์ (ต่อท้ายข้อความ)')
    is_hidden = models.BooleanField(verbose_name='ซ่อนหรือไม่',
                                    default=False)
    rank = models.IntegerField(verbose_name='ลำดับในการแสดง',
                               default=1000)
    created_date = models.DateTimeField(verbose_name='วันเวลาที่สร้าง',
                                        auto_now_add=True)

    class Meta:
        ordering = ['rank', '-created_date']

    def __str__(self):
        return self.alt_text or self.image.name
