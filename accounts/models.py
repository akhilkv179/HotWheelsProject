from django.db import models
from django.contrib.auth.models import AbstractUser
from django.conf import settings






class User(AbstractUser):
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=12,blank=True)
    profile_image = models.ImageField(upload_to="profile_images/",blank=True,null=True)
    is_blocked = models.BooleanField(default=False)


    def __str__(self):
        return self.username

class OTPVerification(models.Model):
    email = models.EmailField()
    otp = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_verified = models.BooleanField(default=False)

    def __str__(self):
        return self.email

class Address(models.Model):

    ADDRESS_TYPE_CHOICES = [
        ("home", "Home"),
        ("work", "Work"),
        ("other", "Other"),
    ]
    user = models.ForeignKey(User,on_delete=models.CASCADE,related_name="addresses")
    full_name = models.CharField(max_length=100)
    phone = models.CharField(max_length=15)
    address_line1 = models.CharField(max_length=255)
    address_line2 = models.CharField(max_length=255,blank=True)
    landmark = models.CharField(max_length=255,blank=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=10)
    address_type = models.CharField(max_length=10,choices=ADDRESS_TYPE_CHOICES,default="home")
    is_default = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.full_name} - {self.city}"