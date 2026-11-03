from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import CandidateProfile, EmployerProfile, User


@receiver(post_save, sender=User)
def create_role_profile(sender, instance, **kwargs):
    if instance.role == User.Role.CANDIDATE:
        CandidateProfile.objects.get_or_create(user=instance)
    elif instance.role == User.Role.EMPLOYER:
        EmployerProfile.objects.get_or_create(user=instance)
