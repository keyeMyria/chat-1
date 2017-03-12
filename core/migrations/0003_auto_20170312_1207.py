# -*- coding: utf-8 -*-
# Generated by Django 1.10.6 on 2017-03-12 12:07
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0002_auto_20170312_1150'),
    ]

    operations = [
        migrations.AddField(
            model_name='thread',
            name='last_message',
            field=models.DateTimeField(null=True),
        ),
        migrations.AlterField(
            model_name='message',
            name='thread',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='messages', to='core.Thread'),
        ),
    ]
