from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0004_order_cdek_order_uuid"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="tbank_payment_id",
            field=models.CharField(
                blank=True,
                db_index=True,
                max_length=50,
                verbose_name="PaymentId T\u2011\u0411\u0430\u043d\u043a\u0430",
            ),
        ),
        migrations.AlterField(
            model_name="order",
            name="status",
            field=models.CharField(
                choices=[
                    ("new", "\u041d\u0435 \u043e\u043f\u043b\u0430\u0447\u0435\u043d"),
                    ("confirmed", "\u041e\u043f\u043b\u0430\u0447\u0435\u043d"),
                    ("in_delivery", "\u041f\u0435\u0440\u0435\u0434\u0430\u043d \u0432 \u0434\u043e\u0441\u0442\u0430\u0432\u043a\u0443"),
                    ("delivered", "\u0414\u043e\u0441\u0442\u0430\u0432\u043b\u0435\u043d"),
                    ("cancelled", "\u041e\u0442\u043c\u0435\u043d\u0451\u043d"),
                    ("refunded", "\u0412\u043e\u0437\u0432\u0440\u0430\u0442"),
                ],
                db_index=True,
                default="new",
                max_length=20,
                verbose_name="\u0421\u0442\u0430\u0442\u0443\u0441",
            ),
        ),
    ]
