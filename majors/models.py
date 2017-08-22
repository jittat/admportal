from django.db import models

class Campus(models.Model):
    title = models.CharField(max_length=100)
    short_title = models.CharField(max_length=50)

    class Meta:
        verbose_name_plural = 'campuses'

    def __str__(self):
        return self.short_title



class Faculty(models.Model):
    title = models.CharField(max_length=100)
    campus = models.ForeignKey('Campus')

    class Meta:
        verbose_name_plural = 'faculties'

    def __str__(self):
        return self.title

    

class AdmissionRound(models.Model):
    number = models.IntegerField()
    subround_number = models.IntegerField(default=0)
    rank = models.IntegerField()

    class Meta:
        ordering = ['rank']

        
    def __str__(self):
        if self.subround_number == 0:
            return 'รอบที่ %d' % (self.number,)
        else:
            return 'รอบที่ %d/%d' % (self.number, self.subround_number)

    
class AdmissionProject(models.Model):
    title = models.CharField(max_length=400)
    short_title = models.CharField(max_length=200)
    admission_round = models.ForeignKey('AdmissionRound')
    campus = models.ForeignKey('Campus',
                               null=True,
                               blank=True)
    
    general_conditions = models.TextField(blank=True)
    column_descriptions = models.TextField(blank=True)

    def __str__(self):
        return self.title
