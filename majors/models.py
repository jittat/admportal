import io
import csv

from django.db import models
from .header_utils import table_header, table_header_column_count
from .header_utils import table_header_as_list_template

class Campus(models.Model):
    title = models.CharField(max_length=100)
    short_title = models.CharField(max_length=50)

    class Meta:
        verbose_name_plural = 'campuses'

    def __str__(self):
        return self.short_title



class Faculty(models.Model):
    title = models.CharField(max_length=100)
    campus = models.ForeignKey('Campus',
                               on_delete=models.PROTECT)

    class Meta:
        verbose_name_plural = 'faculties'

    def __str__(self):
        return self.title

    

class AdmissionRound(models.Model):
    # Rounds numbered from here up are not TCAS rounds but portal-only
    # groupings (e.g. 100 = information for new students).  They are shown
    # by their short_descriptions instead of "รอบที่ N".
    SPECIAL_NUMBER_START = 100

    number = models.IntegerField()
    subround_number = models.IntegerField(default=0)
    rank = models.IntegerField()

    short_descriptions = models.CharField(max_length=400,
                                          blank=True,
                                          verbose_name='รายละเอียดสั้น ๆ (แสดงในหน้าแรก)')
    admission_dates = models.CharField(max_length=200,
                                       blank=True,
                                       verbose_name='กำหนดการ')

    # Portal-only (admapp has no counterpart); import_round_data.py keeps it
    # across re-imports.  At most one round is checked: see save().
    is_default_tab = models.BooleanField(
        default=False,
        verbose_name='เปิดแท็บรอบนี้เป็นค่าเริ่มต้นในข่าวสารหน้าแรก',
        help_text='ถ้าไม่เลือกรอบใด จะเปิดแท็บของรอบที่มีประกาศล่าสุด')

    class Meta:
        ordering = ['rank']

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.is_default_tab:
            (AdmissionRound.objects
             .filter(is_default_tab=True)
             .exclude(pk=self.pk)
             .update(is_default_tab=False))

    @property
    def is_special(self):
        return self.number >= self.SPECIAL_NUMBER_START

    @property
    def number_title(self):
        """Title for the round number as a whole, ignoring the subround."""
        if self.is_special and self.short_descriptions:
            return self.short_descriptions
        return 'รอบที่ %d' % (self.number,)

    def __str__(self):
        if self.subround_number == 0 or self.is_special:
            return self.number_title
        else:
            return 'รอบที่ %d/%d' % (self.number, self.subround_number)


class AdmissionProject(models.Model):
    title = models.CharField(max_length=400)
    short_title = models.CharField(max_length=200)
    admission_rounds = models.ManyToManyField('AdmissionRound',
                                              through='AdmissionProjectRound')
    campus = models.ForeignKey('Campus',
                               on_delete=models.PROTECT,
                               null=True,
                               blank=True)
    
    general_conditions = models.TextField(blank=True)
    column_descriptions = models.TextField(blank=True)
    column_count = models.IntegerField(default=0)
    
    descriptions = models.TextField(blank=True,
                                    verbose_name='รายละเอียดโครงการ')
    short_descriptions = models.CharField(max_length=400,
                                          blank=True,
                                          verbose_name='รายละเอียดโครงการ (สั้น) แสดงในหน้าแรก')
    slots = models.IntegerField(default=0,
                                verbose_name='จำนวนรับ')

    major_detail_visible = models.BooleanField(default=False,
                                               verbose_name='แสดงรายละเอียดสาขา')
    
    is_available = models.BooleanField(default=False)

    max_num_selections = models.IntegerField(default=1,
                                             verbose_name='จำนวนสาขาที่เลือกได้')

    major_table_header_precomputed = models.TextField(blank=True)
    major_description_list_template = models.TextField(blank=True)

    table_header_title = models.CharField(max_length=50,
                                          blank=True,
                                          verbose_name='ชื่อสั้นมากแสดงหัวตาราง')
    default_round_number = models.IntegerField(default=0,
                                               verbose_name='รอบ (default)')
    display_rank = models.IntegerField(default=0,
                                       verbose_name='สำหรับใช้เรียงรายการ')
    
    def __str__(self):
        return self.title

    
    def save(self, *args, **kwargs):
        self.major_table_header_precomputed = self.major_table_header(recompute=True)
        self.column_count = table_header_column_count(self.column_descriptions)
        self.major_description_list_template = table_header_as_list_template(self.column_descriptions)
        
        super(AdmissionProject, self).save(*args, **kwargs)
        
    
    def major_table_header(self, recompute=False):
        if (not recompute) and (self.major_table_header_precomputed):
            return self.major_table_header_precomputed
        
        return table_header(self.column_descriptions,
                            ['หมายเลข',
                             'สาขาวิชา'],
                            ['จำนวนรับ'])


class AdmissionProjectRound(models.Model):
    admission_round = models.ForeignKey('AdmissionRound',
                                        on_delete=models.CASCADE)
    admission_project = models.ForeignKey('AdmissionProject',
                                          on_delete=models.CASCADE)
    admission_dates = models.CharField(max_length=100)

    
class Major(models.Model):
    number = models.IntegerField()
    title = models.CharField(max_length=200)
    faculty = models.ForeignKey('Faculty',
                                on_delete=models.PROTECT)
    admission_project = models.ForeignKey('AdmissionProject',
                                          on_delete=models.PROTECT)

    slots = models.IntegerField()
    slots_comments = models.TextField(blank=True)

    detail_items_csv = models.TextField()

    simplified_title = models.CharField(max_length=200)
    
    class Meta:
        ordering = ['number']
    
    def __str__(self):
        return self.title

    def get_detail_items(self):
        csv_io = io.StringIO(self.detail_items_csv)
        reader = csv.reader(csv_io)
        for row in reader:
            return row

    def detail_items_as_list_display(self):
        items = [item.replace("\n","<br />") for item in self.get_detail_items()]
        return self.admission_project.major_description_list_template.format(*items)
        
    @staticmethod
    def simplify_title(title):
        rem_chars = "์ ()"
        
        return ''.join([c for c in title if c not in rem_chars])
