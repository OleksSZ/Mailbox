import subprocess
import sys
import os
from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpResponse, JsonResponse
from django.conf import settings
from .models import MailboxAccount
from django.contrib import admin

@staff_member_required
def run_playwright_script(request):
    os.system("pkill -f mailbox_register.py")
    os.system("pkill -f chromium")
    if request.method == 'POST':
        countries_list = request.POST.getlist('countries')
        account_count = request.POST.get('account_count')

        countries_arg = ",".join(countries_list) if countries_list else "IT"

        script_path = os.path.join(settings.BASE_DIR, 'modules', 'mailbox_register.py')
        log_file_path = os.path.join(settings.BASE_DIR, 'script_logs.txt')

        open(log_file_path, 'w', encoding='utf-8').close()

        log_file = open(log_file_path, 'a', encoding='utf-8')

        custom_env = os.environ.copy()
        custom_env["PYTHONIOENCODING"] = "utf-8"

        subprocess.Popen(
            [sys.executable, '-u', script_path, countries_arg, str(account_count)],
            stdout=log_file,
            stderr=subprocess.STDOUT,
            env=custom_env
        )

        return render(request, 'admin/run_script_form.html', {'script_running': True})

    return render(request, 'admin/run_script_form.html', {'script_running': False})

@staff_member_required
def get_script_logs(request):
    log_file_path = os.path.join(settings.BASE_DIR, 'script_logs.txt')
    if os.path.exists(log_file_path):
        with open(log_file_path, 'r', encoding='utf-8', errors='replace') as f:
            return HttpResponse(f.read(), content_type='text/plain')
    return HttpResponse("Очікування логів...", content_type='text/plain')

@staff_member_required
def stop_script_view(request):
    os.system("pkill -f mailbox_register.py")
    os.system("pkill -f chromium")
    os.system("pkill -f chrome")

    log_file_path = os.path.join(settings.BASE_DIR, 'script_logs.txt')
    try:
        with open(log_file_path, 'a', encoding='utf-8') as f:
            f.write("\n\nГенрацію зупинено\n")
    except Exception:
        pass

    return HttpResponse(status=204)

def api_get_accounts(request):
    country = request.GET.get('country')

    if country and country != 'ALL':
        accounts = MailboxAccount.objects.filter(country=country.upper())
    else:
        accounts = MailboxAccount.objects.all()

    accounts_data = list(accounts.values(
        'id', 'email', 'password', 'first_name', 'last_name',
        'country', 'gender', 'status', 'created_at', 'provider'
    ))

    return JsonResponse({
        'total_count': accounts.count(),
        'country_filter': country.upper() if country else 'ALL',
        'accounts': accounts_data
    }, json_dumps_params={'ensure_ascii': False})