from .models import AdminToken


class AdminRequired:
    """
    Mixin for function-based views.  Sets request.admin_user on success.
    Returns (admin, None) on success, (None, Response) on failure.
    """

    @staticmethod
    def resolve(request):
        from rest_framework.response import Response

        header = request.META.get('HTTP_AUTHORIZATION', '')
        if not header.startswith('AdminToken '):
            return None, Response({'error': 'Authentication required'}, status=401)

        token_value = header[len('AdminToken '):].strip()
        try:
            token = AdminToken.objects.select_related('admin__django_user').get(token=token_value)
        except AdminToken.DoesNotExist:
            return None, Response({'error': 'Invalid token'}, status=401)

        if not token.is_valid():
            token.delete()
            return None, Response({'error': 'Token expired'}, status=401)

        if not token.admin.is_active:
            return None, Response({'error': 'Account disabled'}, status=403)

        request.admin_user = token.admin
        return token.admin, None
