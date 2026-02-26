from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0003_add_delivery_tariff_code"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="cdek_order_uuid",
            field=models.CharField(
                blank=True,
                help_text="UUID, присвоенный СДЭК при регистрации заказа через API",
                max_length=50,
                verbose_name="UUID заказа в СДЭК",
            ),
        ),
    ]
