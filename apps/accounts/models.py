from django.conf import settings
from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator
from django.db import models

from .upload_validators import resume_upload_path, validate_resume_file


class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("An email address is required.")
        if not password:
            raise ValueError("A password is required.")
        if extra_fields.get("role") not in self.model.Role.values:
            raise ValueError("A valid role is required.")

        email = self.normalize_email(email.strip()).lower()
        extra_fields["phone"] = extra_fields.get("phone") or None
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("role", self.model.Role.ADMIN)
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        if extra_fields["role"] != self.model.Role.ADMIN:
            raise ValueError("A superuser must have the admin role.")
        if not extra_fields["is_staff"]:
            raise ValueError("A superuser must have is_staff=True.")
        if not extra_fields["is_superuser"]:
            raise ValueError("A superuser must have is_superuser=True.")

        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = "admin", "Admin"
        EMPLOYER = "employer", "Employer"
        CANDIDATE = "candidate", "Candidate"

    username = None
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=32, blank=True, null=True, unique=True)
    role = models.CharField(max_length=20, choices=Role.choices, db_index=True)
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    def clean(self):
        super().clean()
        self.email = self.email.strip().lower()
        if self.phone is not None:
            self.phone = self.phone.strip() or None

    def __str__(self):
        return self.email


class CandidateProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="candidate_profile",
    )
    skills = models.JSONField(default=list, blank=True)
    education = models.TextField(blank=True)
    experience = models.TextField(blank=True)
    expected_salary = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )
    resume = models.FileField(
        upload_to=resume_upload_path,
        validators=[validate_resume_file],
        blank=True,
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Candidate profile: {self.user.email}"


class EmployerProfile(models.Model):
    class CompanySize(models.TextChoices):
        SIZE_1_10 = "1-10", "1-10 employees"
        SIZE_11_50 = "11-50", "11-50 employees"
        SIZE_51_200 = "51-200", "51-200 employees"
        SIZE_201_500 = "201-500", "201-500 employees"
        SIZE_501_1000 = "501-1000", "501-1,000 employees"
        SIZE_1001_PLUS = "1001+", "1,001+ employees"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="employer_profile",
    )
    company_name = models.CharField(max_length=255, blank=True)
    domain = models.URLField(blank=True)
    company_size = models.CharField(
        max_length=20,
        choices=CompanySize.choices,
        blank=True,
    )
    is_verified = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Employer profile: {self.user.email}"
