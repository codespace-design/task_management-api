from rest_framework.views import exception_handler as default_exception_handler


def api_exception_handler(exc, context):
    response = default_exception_handler(exc, context)
    if response is None:
        return None

    details = response.data
    if isinstance(details, str):
        message = details
    elif isinstance(details, dict) and "detail" in details:
        message = str(details["detail"])
    elif response.status_code == 400:
        message = "Validation failed."
    else:
        message = "The request could not be completed."

    response.data = {
        "success": False,
        "status_code": response.status_code,
        "message": message,
        "errors": (
            details
            if isinstance(details, (dict, list))
            and "detail" not in details
            else None
        ),
    }
    return response
