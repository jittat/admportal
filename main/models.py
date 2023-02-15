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
