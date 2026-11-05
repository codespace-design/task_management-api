from pathlib import Path

from django.http import FileResponse, Http404
from django.urls import reverse
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import CandidateProfile, EmployerProfile, User
from .permissions import IsProfileOwnerOrAdmin
from .profile_serializers import (
    CandidateProfileSerializer,
    EmployerProfileSerializer,
    ResumeUploadSerializer,
)


class ProfileAPIView(APIView):
    permission_classes = [IsProfileOwnerOrAdmin]
    profile_model = None
    profile_role = None
    serializer_class = None

    def get_target_user(self, request, user_id=None):
        if user_id is None:
            target = request.user
        else:
            if request.user.role != User.Role.ADMIN and user_id != request.user.pk:
                raise PermissionDenied("You can only access your own profile.")
            try:
                target = User.objects.get(pk=user_id)
            except User.DoesNotExist as error:
                raise Http404 from error

        self.check_object_permissions(request, target)
        if target.role != self.profile_role:
            raise Http404
        return target

    def get_profile(self, request, user_id=None, include_inactive=False):
        target = self.get_target_user(request, user_id)
        profiles = self.profile_model.objects.filter(user=target)
        if not include_inactive:
            profiles = profiles.filter(is_active=True)
        try:
            profile = profiles.get()
        except self.profile_model.DoesNotExist as error:
            raise Http404 from error
        self.check_object_permissions(request, profile)
        return profile

    def get_serializer(self, *args, **kwargs):
        kwargs.setdefault("context", {"request": self.request})
        return self.serializer_class(*args, **kwargs)

    def get(self, request, user_id=None):
        profile = self.get_profile(request, user_id)
        return Response(self.get_serializer(profile).data)

    def post(self, request, user_id=None):
        target = self.get_target_user(request, user_id)
        profile = self.profile_model.objects.filter(user=target).first()
        created = profile is None
        if profile is not None:
            self.check_object_permissions(request, profile)
        serializer = self.get_serializer(
            profile,
            data=request.data,
        )
        serializer.is_valid(raise_exception=True)
        profile = serializer.save(user=target, is_active=True)
        response_status = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return Response(self.get_serializer(profile).data, status=response_status)

    def put(self, request, user_id=None):
        return self.update(request, user_id, partial=False)

    def patch(self, request, user_id=None):
        return self.update(request, user_id, partial=True)

    def update(self, request, user_id, partial):
        profile = self.get_profile(request, user_id)
        serializer = self.get_serializer(profile, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        return Response(self.get_serializer(serializer.save()).data)

    def delete(self, request, user_id=None):
        profile = self.get_profile(request, user_id)
        profile.is_active = False
        profile.save(update_fields=("is_active", "updated_at"))
        return Response(status=status.HTTP_204_NO_CONTENT)


class CandidateProfileAPIView(ProfileAPIView):
    profile_model = CandidateProfile
    profile_role = User.Role.CANDIDATE
    serializer_class = CandidateProfileSerializer


class EmployerProfileAPIView(ProfileAPIView):
    profile_model = EmployerProfile
    profile_role = User.Role.EMPLOYER
    serializer_class = EmployerProfileSerializer


class CandidateResumeAPIView(ProfileAPIView):
    profile_model = CandidateProfile
    profile_role = User.Role.CANDIDATE
    serializer_class = CandidateProfileSerializer

    def get(self, request, user_id=None):
        profile = self.get_profile(request, user_id)
        if not profile.resume or not profile.resume.storage.exists(profile.resume.name):
            raise Http404

        response = FileResponse(
            profile.resume.open("rb"),
            as_attachment=True,
            filename=f"resume{Path(profile.resume.name).suffix}",
            content_type="application/octet-stream",
        )
        response["X-Content-Type-Options"] = "nosniff"
        return response

    def post(self, request, user_id=None):
        return self.upload(request, user_id)

    def put(self, request, user_id=None):
        return self.upload(request, user_id)

    def upload(self, request, user_id):
        profile = self.get_profile(request, user_id)
        serializer = ResumeUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        uploaded_file = serializer.validated_data["resume"]
        previous_name = profile.resume.name
        profile.resume.save(uploaded_file.name, uploaded_file, save=True)
        if previous_name and previous_name != profile.resume.name:
            profile.resume.storage.delete(previous_name)
        return Response(
            {
                "detail": "Resume uploaded successfully.",
                "download_url": self.get_download_url(request, profile.user_id),
            },
            status=status.HTTP_200_OK,
        )

    def delete(self, request, user_id=None):
        profile = self.get_profile(request, user_id)
        if profile.resume:
            storage = profile.resume.storage
            previous_name = profile.resume.name
            profile.resume = ""
            profile.save(update_fields=("resume", "updated_at"))
            storage.delete(previous_name)
        return Response(status=status.HTTP_204_NO_CONTENT)

    def get_download_url(self, request, profile_user_id):
        path = reverse(
            "candidate-resume-detail",
            kwargs={"user_id": profile_user_id},
        )
        return request.build_absolute_uri(path)
