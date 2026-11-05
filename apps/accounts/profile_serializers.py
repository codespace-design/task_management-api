from rest_framework import serializers

from .models import CandidateProfile, EmployerProfile, User


class CandidateProfileSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(read_only=True)
    user_email = serializers.EmailField(source="user.email", read_only=True)
    expected_salary = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=0,
        allow_null=True,
        required=False,
    )

    class Meta:
        model = CandidateProfile
        fields = (
            "id",
            "user",
            "user_email",
            "skills",
            "education",
            "experience",
            "expected_salary",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "is_active", "created_at", "updated_at")

    def validate_skills(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("Skills must be a list of strings.")
        if any(not isinstance(skill, str) or not skill.strip() for skill in value):
            raise serializers.ValidationError("Each skill must be a non-empty string.")
        return list(dict.fromkeys(skill.strip() for skill in value))


class EmployerProfileSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(read_only=True)
    user_email = serializers.EmailField(source="user.email", read_only=True)
    company_name = serializers.CharField(max_length=255, allow_blank=False)
    is_verified = serializers.BooleanField(required=False)

    class Meta:
        model = EmployerProfile
        fields = (
            "id",
            "user",
            "user_email",
            "company_name",
            "domain",
            "company_size",
            "is_verified",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "is_active", "created_at", "updated_at")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if request is None or request.user.role != User.Role.ADMIN:
            self.fields["is_verified"].read_only = True
