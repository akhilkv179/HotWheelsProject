from django.db import models


class Banner(models.Model):
    title = models.CharField(max_length=255)
    image_url = models.CharField(max_length=255)
    link_url = models.CharField(max_length=255)
    target_type = models.CharField(max_length=100)
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    sort_order = models.IntegerField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title