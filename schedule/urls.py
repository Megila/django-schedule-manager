from django.urls import path
from .views import CustomLoginView, user_profile_view, general_schedule, my_schedule, edit_template_schedule, edit_operational_schedule
from django.contrib.auth.views import LogoutView

urlpatterns = [
    path('login/', CustomLoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(next_page='login'), name='logout'),
    path('', general_schedule, name='general_schedule'),
    path('my-schedule/', my_schedule, name='my_schedule'),
    path('edit-template/', edit_template_schedule, name='edit_template_schedule'),
    path('edit-operational/', edit_operational_schedule, name='edit_operational_schedule'),
    path('profile/', user_profile_view, name='profile'),
    path('profile/<str:username>/', user_profile_view, name='user_profile'),
]
