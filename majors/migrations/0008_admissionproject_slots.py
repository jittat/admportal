# -*- coding: utf-8 -*-
# Generated by Django 1.11.4 on 2017-08-25 06:02
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('majors', '0007_auto_20170825_0547'),
    ]

    operations = [
        migrations.AddField(
            model_name='admissionproject',
            name='slots',
            field=models.IntegerField(default=0, verbose_name='จำนวนรับ'),
        ),
    ]
