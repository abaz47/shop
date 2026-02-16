# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0003_split_payment_delivery'),
    ]

    operations = [
        migrations.CreateModel(
            name='SiteImage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200, verbose_name='Название')),
                ('slug', models.SlugField(help_text='Используется для получения ссылки на изображение', max_length=200, unique=True, verbose_name='Slug (для ссылки)')),
                ('image', models.ImageField(upload_to='site_images/%Y/%m/', verbose_name='Файл изображения')),
                ('category', models.CharField(choices=[('payment', 'Оплата (логотипы платежных систем)'), ('delivery', 'Доставка (логотипы служб доставки)'), ('other', 'Прочее')], default='other', max_length=20, verbose_name='Категория')),
                ('description', models.TextField(blank=True, verbose_name='Описание')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')),
            ],
            options={
                'verbose_name': 'изображение сайта',
                'verbose_name_plural': 'изображения сайта',
                'ordering': ['category', 'name'],
            },
        ),
    ]
