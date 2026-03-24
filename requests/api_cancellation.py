from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, status
from .models import CancellationReason


class CancellationReasonsView(APIView):
    """Get cancellation reasons for the current user's role"""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user_role = request.user.role
        
        reasons = CancellationReason.objects.filter(
            role=user_role,
            is_active=True
        ).order_by('order')
        
        reasons_data = []
        for reason in reasons:
            reason_data = {
                'id': reason.id,
                'reason': reason.reason,
                'requires_custom_text': reason.requires_custom_text,
                'order': reason.order
            }
            reasons_data.append(reason_data)
        
        return Response({
            'role': user_role,
            'reasons': reasons_data
        })
