from django.db import transaction
from rest_framework import serializers

from .models import Job, JobSkill


class SkillNamesField(serializers.Field):
    def to_representation(self, value):
        return [skill.name for skill in value.all()]

    def to_internal_value(self, data):
        if not isinstance(data, list):
            raise serializers.ValidationError("Skills must be a list of strings.")

        names = []
        seen = set()
        for value in data:
            if not isinstance(value, str) or not value.strip():
                raise serializers.ValidationError(
                    "Each skill must be a non-empty string."
                )
            name = value.strip()
            normalized_name = name.casefold()
            if len(name) > 80 or len(normalized_name) > 80:
                raise serializers.ValidationError(
                    "Skill names must be 80 characters or fewer."
                )
            if normalized_name not in seen:
                names.append(name)
                seen.add(normalized_name)
        return names


class JobSerializer(serializers.ModelSerializer):
    employer = serializers.IntegerField(source="employer_id", read_only=True)
    skills = SkillNamesField(source="skill_entries", required=False)
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
    minimum_experience_years = serializers.IntegerField(
        min_value=0,
        allow_null=True,
        required=False,
    )
    maximum_experience_years = serializers.IntegerField(
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
            "minimum_experience_years",
            "maximum_experience_years",
            "minimum_salary",
            "maximum_salary",
            "location",
            "job_type",
            "status",
            "is_featured",
            "employer",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "status",
            "is_featured",
            "employer",
            "created_at",
            "updated_at",
        )

    def validate_title(self, value):
        title = value.strip()
        if not title:
            raise serializers.ValidationError("Title cannot be blank.")
        return title

    def validate(self, attrs):
        minimum_salary = attrs.get(
            "minimum_salary",
            getattr(self.instance, "minimum_salary", None),
        )
        maximum_salary = attrs.get(
            "maximum_salary",
            getattr(self.instance, "maximum_salary", None),
        )
        minimum_experience = attrs.get(
            "minimum_experience_years",
            getattr(self.instance, "minimum_experience_years", None),
        )
        maximum_experience = attrs.get(
            "maximum_experience_years",
            getattr(self.instance, "maximum_experience_years", None),
        )
        if (
            minimum_salary is not None
            and maximum_salary is not None
            and minimum_salary > maximum_salary
        ):
            raise serializers.ValidationError(
                {"maximum_salary": "Must be greater than or equal to minimum_salary."}
            )
        if (
            minimum_experience is not None
            and maximum_experience is not None
            and minimum_experience > maximum_experience
        ):
            raise serializers.ValidationError(
                {
                    "maximum_experience_years": (
                        "Must be greater than or equal to minimum_experience_years."
                    )
                }
            )
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        skill_names = validated_data.pop("skill_entries", [])
        job = super().create(validated_data)
        self._replace_skills(job, skill_names)
        return job

    @transaction.atomic
    def update(self, instance, validated_data):
        skill_names = validated_data.pop("skill_entries", None)
        job = super().update(instance, validated_data)
        if skill_names is not None:
            self._replace_skills(job, skill_names)
        return job

    @staticmethod
    def _replace_skills(job, skill_names):
        job.skill_entries.all().delete()
        JobSkill.objects.bulk_create(
            [
                JobSkill(
                    job=job,
                    name=name,
                    normalized_name=name.casefold(),
                )
                for name in skill_names
            ]
        )
