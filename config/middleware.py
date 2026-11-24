from django.http import JsonResponse


class ApiServerErrorMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.path.startswith("/api/") and response.status_code == 500:
            return JsonResponse(
                {
                    "success": False,
                    "status_code": 500,
                    "message": "An unexpected server error occurred.",
                    "errors": None,
                },
                status=500,
            )
        return response
