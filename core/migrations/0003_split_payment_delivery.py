# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0002_alter_legalpage_slug'),
    ]

    operations = [
        migrations.AlterField(
            model_name='legalpage',
            name='slug',
            field=models.SlugField(
                choices=[
                    ('terms', 'Пользовательское соглашение'),
                    ('privacy', 'Политика конфиденциальности'),
                    ('offer', 'Оферта'),
                    ('requisites', 'Реквизиты'),
                    ('return', 'Возврат и обмен'),
                    ('payment', 'Оплата'),
                    ('delivery', 'Доставка'),
                    ('contacts', 'Контакты'),
                ],
                unique=True,
                verbose_name='Идентификатор (slug)'
            ),
        ),
    ]
