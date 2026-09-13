from django.db import models
from django.contrib.auth.models import AbstractUser







class user(AbstractUser):
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=12,blank=True)


    def __str__(self):
        return self.username

    