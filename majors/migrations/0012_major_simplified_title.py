# -*- coding: utf-8 -*-
# Generated by Django 1.11.5 on 2017-09-16 02:07
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('majors', '0011_admissionproject_major_detail_visible'),
    ]

    operations = [
        migrations.AddField(
            model_name='major',
            name='simplified_title',
            field=models.CharField(default='', max_length=200),
            preserve_default=False,
        ),
    ]
