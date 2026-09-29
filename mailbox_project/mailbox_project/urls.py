from django.contrib import admin
from django.urls import path
from other.Mailbox.mailbox_project.parser_app.views import run_playwright_script, get_script_logs, stop_script_view, api_get_accounts

urlpatterns = [
    path('admin/run-script/', run_playwright_script, name='run_playwright_script'),
    path('admin/script-logs/', get_script_logs, name='get_script_logs'),
    path('admin/run-script/stop/', stop_script_view, name='stop_script_view'),
    path('api/v1/accounts/', api_get_accounts, name='api_get_accounts'),
    path('admin/', admin.site.urls),
]