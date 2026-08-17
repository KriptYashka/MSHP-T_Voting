from .views import get_role


def current_role(request):
    return {'current_role': get_role(request.user)}
