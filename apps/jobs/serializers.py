from rest_framework import serializers

from .models import Job


class JobSerializer(serializers.ModelSerializer):
    employer = serializers.IntegerField(source="employer_id", read_only=True)
    minimum_salary = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=0,
        allow_null=True,
        required=False,
    )
    maximum_salary = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=0,
        allow_null=True,
        required=False,
    )

    class Meta:
        model = Job
        fields = (
            "id",
            "title",
            "description",
            "skills",
            "experience",
            "minimum_salary",
            "maximum_salary",
            "location",
            "job_type",
            "status",
            "employer",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "status", "employer", "created_at", "updated_at")

    def validate_title(self, value):
        title = value.strip()
        if not title:
            raise serializers.ValidationError("Title cannot be blank.")
        return title

    def validate_skills(self, value):
        if not isinstance(value, list) or any(
            not isinstance(skill, str) or not skill.strip() for skill in value
        ):
            raise serializers.ValidationError(
                "Skills must be a list of non-empty strings."
            )
        return list(dict.fromkeys(skill.strip() for skill in value))

    def validate(self, attrs):
        minimum_salary = attrs.get(
            "minimum_salary",
            getattr(self.instance, "minimum_salary", None),
        )
        maximum_salary = attrs.get(
            "maximum_salary",
            getattr(self.instance, "maximum_salary", None),
        )
        if (
            minimum_salary is not None
            and maximum_salary is not None
            and minimum_salary > maximum_salary
        ):
            raise serializers.ValidationError(
                {"maximum_salary": "Must be greater than or equal to minimum_salary."}
            )
        return attrs
