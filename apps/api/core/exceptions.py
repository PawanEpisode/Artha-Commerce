from rest_framework.views import exception_handler


def api_exception_handler(exc, context):
    """Every error leaves the API in one shape: {"error": {"code", "message", "details"}}."""
    response = exception_handler(exc, context)
    if response is None:
        return None
    details = response.data
    message = details.get("detail") if isinstance(details, dict) and "detail" in details else "Request failed."
    response.data = {
        "error": {
            "code": getattr(exc, "default_code", "error"),
            "message": str(message),
            "details": None if isinstance(details, dict) and set(details) == {"detail"} else details,
        }
    }
    return response
