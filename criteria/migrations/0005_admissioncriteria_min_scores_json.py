# Generated by Django 2.2.17 on 2020-11-23 01:25

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('criteria', '0004_majorcuptcode_admission_project_list'),
    ]

    operations = [
        migrations.AddField(
            model_name='admissioncriteria',
            name='min_scores_json',
            field=models.TextField(blank=True),
        ),
    ]
