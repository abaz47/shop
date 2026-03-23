from django.core.validators import FileExtensionValidator
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0005_remove_sitesettings"),
    ]

    operations = [
        migrations.AlterField(
            model_name="siteimage",
            name="image",
            field=models.FileField(
                upload_to="site_images/%Y/%m/",
                validators=[
                    FileExtensionValidator(
                        allowed_extensions=[
                            "svg",
                            "png",
                            "jpg",
                            "jpeg",
                            "webp",
                            "gif",
                        ]
                    )
                ],
                verbose_name="Файл изображения",
            ),
        ),
    ]
