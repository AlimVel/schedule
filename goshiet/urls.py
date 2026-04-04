from django.urls import path
from core import views

urlpatterns = [
    path('', views.index, name='index'),
    path('auth/', views.auth, name='auth'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('teacher-dashboard/', views.teacher_dashboard, name='teacher_dashboard'), 
    path('schedule/', views.schedule, name='schedule'),
    path('logout/', views.logout_view, name='logout'),
    path('generate-invite/', views.generate_invite, name='generate_invite'),
    path('invite/<uuid:token>/', views.teacher_register, name='teacher_register'),
]