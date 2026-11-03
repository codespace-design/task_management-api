from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .models import User


class RegisterSerializer(serializers.ModelSerializer):
    email = serializers.EmailField()
    role = serializers.ChoiceField(
        choices=[
            (User.Role.EMPLOYER, User.Role.EMPLOYER.label),
            (User.Role.CANDIDATE, User.Role.CANDIDATE.label),
        ]
    )
    password = serializers.CharField(
        write_only=True,
        style={"input_type": "password"},
        trim_whitespace=False,
    )

    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "phone",
            "role",
            "password",
            "is_verified",
            "created_at",
        )
        read_only_fields = ("id", "is_verified", "created_at")

    def validate_email(self, value):
        email = value.strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return email

    def validate_phone(self, value):
        phone = value.strip()
        if phone and User.objects.filter(phone=phone).exists():
            raise serializers.ValidationError("A user with this phone already exists.")
        return phone or None

    def validate(self, attrs):
        user = User(email=attrs["email"], phone=attrs.get("phone", ""))
        try:
            validate_password(attrs["password"], user=user)
        except DjangoValidationError as error:
            raise serializers.ValidationError({"password": error.messages}) from error
        return attrs

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)
