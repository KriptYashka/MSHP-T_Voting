from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path

from app import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.index_page, name='index'),
    path('login/', views.login_page, name='login'),
    path('logout/', views.logout_page, name='logout'),
    path('projects/', views.projects_list, name='projects'),
    path('projects/create/', views.project_create, name='project_create'),
    path('projects/<int:project_id>/', views.project_detail, name='project_detail'),
    path('projects/<int:project_id>/edit/', views.project_edit, name='project_edit'),
    path('projects/<int:project_id>/screenshot/<int:screenshot_id>/delete/', views.screenshot_delete, name='screenshot_delete'),
    path('voting/', views.voting_page, name='voting'),
    path('expert-rate/', views.expert_rate, name='expert_rate'),
    path('admin-panel/', views.admin_panel, name='admin_panel'),
    path('admin-panel/results/', views.admin_results, name='admin_results'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
