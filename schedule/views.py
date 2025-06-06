from django.contrib.auth.views import LoginView
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import User
from django.utils.timezone import localdate
from django.utils.dateparse import parse_date
from django.core.exceptions import ValidationError
from datetime import date, timedelta, time, datetime
from .models import OperationalSchedule, ScheduleTemplate, Project, UserProfile
from django.views.decorators.cache import never_cache
from .forms import CustomLoginForm

DAYS_OF_WEEK = [
    (0, 'Понедельник'),
    (1, 'Вторник'),
    (2, 'Среда'),
    (3, 'Четверг'),
    (4, 'Пятница'),
    (5, 'Суббота'),
    (6, 'Воскресенье'),
]

WORK_START = time(9, 0)
WORK_END = time(18, 0)
REFERENCE_DATE = date(2025, 1, 1)

class CustomLoginView(LoginView):
    template_name = 'schedule/login.html'
    authentication_form = CustomLoginForm

def get_week_type(user, date):
    profile = user.userprofile
    if profile.schedule_mode == 'one':
        return 'one'
    else:
        week_number = (date - REFERENCE_DATE).days // 7
        return 'one' if week_number % 2 == 0 else 'two'

def get_current_week_number(reference_date, user):
    if user.userprofile.schedule_mode == 'one':
        return 1
    base_date = REFERENCE_DATE
    delta_weeks = (reference_date - base_date).days // 7
    return 1 if delta_weeks % 2 == 0 else 2

def subtract_intervals(template, operations):
    result = []
    current_start = template.start_time
    template_end = template.end_time

    for op in sorted(operations, key=lambda x: x.start_time):
        if op.end_time <= current_start or op.start_time >= template_end:
            continue
        if op.start_time > current_start:
            result.append((current_start, op.start_time))
        current_start = max(current_start, op.end_time)

    if current_start < template_end:
        result.append((current_start, template_end))

    return result

def has_time_overlap(new_start, new_end, entries, exclude_id=None):
    for entry in entries:
        if exclude_id and entry.id == exclude_id:
            continue
        if new_start < entry.end_time and new_end > entry.start_time:
            return True
    return False

def build_schedule_blocks(entries, current_date):
    blocks = []
    current_time = WORK_START

    entries = sorted(entries, key=lambda x: x.start_time)

    for entry in entries:
        if entry.end_time <= current_time:
            continue

        if entry.start_time > current_time:
            duration = (datetime.combine(current_date, entry.start_time) - datetime.combine(current_date, current_time)).total_seconds() / 3600
            blocks.append({
                'type': 'empty',
                'duration': round(duration, 4),
            })

        start_offset = entry.start_time.hour + entry.start_time.minute / 60
        duration = (datetime.combine(current_date, entry.end_time) - datetime.combine(current_date, entry.start_time)).total_seconds() / 3600

        availability = getattr(entry, 'availability', '').lower()
        status_class = 'available' if availability == 'доступен' else 'unavailable'

        blocks.append({
            'type': 'activity',
            'activity': entry.activity,
            'availability': entry.availability,
            'start_time': entry.start_time,
            'end_time': entry.end_time,
            'duration': round(duration, 4),
            'start_offset': round(start_offset, 4),
            'source': getattr(entry, 'source', 'template'),
            'status_class': status_class,
        })

        current_time = entry.end_time

    if current_time < WORK_END:
        duration = (datetime.combine(current_date, WORK_END) - datetime.combine(current_date, current_time)).total_seconds() / 3600
        blocks.append({
            'type': 'empty',
            'duration': round(duration, 4),
        })

    return blocks

@never_cache
@login_required
def user_profile_view(request, username=None):
    if username:
        if username == request.user.username:
            return redirect('profile')
        user_view = get_object_or_404(User, username=username)
    else:
        user_view = request.user

    profile = user_view.userprofile
    is_owner = user_view == request.user

    if request.method == 'POST' and is_owner:
        selected_mode = request.POST.get('schedule_mode')
        if selected_mode in ['one', 'two']:
            profile.schedule_mode = selected_mode
            profile.save()

    return render(request, 'schedule/profile.html', {
        'user_view': user_view,
        'profile': profile,
        'projects': user_view.projects.all(),
        'is_owner': is_owner,
    })

@never_cache
@login_required
def general_schedule(request):
    date_str = request.GET.get('date')
    try:
        selected_date = parse_date(date_str) if date_str else localdate()
        if selected_date is None:
            raise ValueError
    except (ValueError, TypeError):
        selected_date = localdate()

    previous_date = selected_date - timedelta(days=1)
    next_date = selected_date + timedelta(days=1)
    weekday = selected_date.weekday()

    project_id = request.GET.get('project')
    if project_id:
        try:
            project = Project.objects.get(id=project_id)
            users = project.users.all()
        except Project.DoesNotExist:
            users = User.objects.all()
            project = None
    else:
        users = User.objects.all()
        project = None

    hours = list(range(9, 18))
    user_slots = {}

    for user in users:
        week_type = get_week_type(user, selected_date)
        tmpl_entries = ScheduleTemplate.objects.filter(user=user, day=weekday, week_type=week_type)
        op_entries = OperationalSchedule.objects.filter(user=user, date=selected_date)

        combined_entries = []

        for op in op_entries:
            combined_entries.append(op)

        for tmpl in tmpl_entries:
            time_slots = subtract_intervals(tmpl, op_entries)
            for start, end in time_slots:
                tmpl.start_time = start
                tmpl.end_time = end
                combined_entries.append(tmpl)

        user_slots[user] = build_schedule_blocks(combined_entries, selected_date)

    return render(request, 'schedule/general_schedule.html', {
        'user_slots': user_slots,
        'selected_date': selected_date,
        'previous_date': previous_date,
        'next_date': next_date,
        'project': project,
        'projects': Project.objects.all(),
        'hours': hours,
        'today': localdate(),
    })

@never_cache
@login_required
def my_schedule(request):
    user = request.user
    mode = request.GET.get('mode', 'operational')
    today = localdate()
    week_number_param = request.GET.get('week')

    week_number = int(week_number_param) if week_number_param else get_current_week_number(today, user)

    start_of_week = today - timedelta(days=today.weekday())
    if week_number == 2:
        start_of_week += timedelta(weeks=1)

    schedule_by_day = []

    for day_offset in range(7):
        current_date = start_of_week + timedelta(days=day_offset)
        weekday = current_date.weekday()
        week_type = get_week_type(user, current_date)

        entries = []

        if mode == 'template':
            entries = list(ScheduleTemplate.objects.filter(user=user, day=weekday, week_type=week_type))
            for entry in entries:
                entry.source = 'template'
        else:
            op_entries = list(OperationalSchedule.objects.filter(user=user, date=current_date))
            for entry in op_entries:
                entry.source = 'operational'

            tmpl_entries = ScheduleTemplate.objects.filter(user=user, day=weekday, week_type=week_type)
            entries = op_entries.copy()

            for tmpl in tmpl_entries:
                time_slots = subtract_intervals(tmpl, op_entries)
                for start, end in time_slots:
                    tmpl_copy = ScheduleTemplate(
                        user=tmpl.user,
                        week_type=tmpl.week_type,
                        day=tmpl.day,
                        activity=tmpl.activity,
                        availability=tmpl.availability,
                        start_time=start,
                        end_time=end
                    )
                    tmpl_copy.source = 'template'
                    entries.append(tmpl_copy)

        blocks = build_schedule_blocks(entries, current_date)
        schedule_by_day.append((current_date, blocks))

    hours = list(range(9, 18))

    return render(request, 'schedule/my_schedule.html', {
        'schedule_by_day': schedule_by_day,
        'mode': mode,
        'week_number': week_number,
        'DAYS_OF_WEEK': DAYS_OF_WEEK,
        'hours': hours,
    })

@never_cache
@login_required
def edit_template_schedule(request):
    user = request.user
    profile = user.userprofile
    schedule_mode = profile.schedule_mode
    today = localdate()
    week_number_param = request.GET.get('week') or request.POST.get('week')
    selected_week = int(week_number_param) if week_number_param else get_current_week_number(today, user)
    selected_day = request.GET.get('day') or request.POST.get('day')
    error_message = None

    new_activity = ''
    new_availability = ''
    new_start_time = ''
    new_end_time = ''

    try:
        selected_week = int(selected_week)
    except (ValueError, TypeError):
        selected_week = None

    try:
        selected_day = int(selected_day)
    except (ValueError, TypeError):
        selected_day = None

    if schedule_mode == 'one':
        selected_week = 1

    entries = []
    week_str = None

    if selected_week is not None:
        week_str = 'one' if selected_week == 1 else 'two'

    if week_str and selected_day is not None:
        entries = ScheduleTemplate.objects.filter(user=user, week_type=week_str, day=selected_day)

        if request.method == 'POST':
            action = request.POST.get('action')

            # Обработка удаления
            if action and action.startswith('delete_'):
                try:
                    entry_id = int(action.replace('delete_', ''))
                    ScheduleTemplate.objects.get(id=entry_id, user=user).delete()
                    return redirect(f"{request.path}?week={selected_week}&day={selected_day}")
                except (ValueError, ScheduleTemplate.DoesNotExist):
                    error_message = "Не удалось удалить запись."

            elif action == 'save':
                for entry in entries:
                    activity = request.POST.get(f'activity_{entry.id}')
                    availability = request.POST.get(f'availability_{entry.id}')
                    start_time = request.POST.get(f'start_time_{entry.id}')
                    end_time = request.POST.get(f'end_time_{entry.id}')

                    try:
                        new_start = datetime.strptime(start_time, "%H:%M").time()
                        new_end = datetime.strptime(end_time, "%H:%M").time()

                        if new_start >= new_end:
                            error_message = "Время начала должно быть раньше времени окончания."
                            break
                        if new_start < WORK_START or new_end > WORK_END:
                            error_message = "Рабочее время должно быть в диапазоне с 09:00 до 18:00."
                            break
                        if has_time_overlap(new_start, new_end, entries, exclude_id=entry.id):
                            error_message = "В расписании есть ошибка, связанная с пересечением времени."
                            break

                        entry.start_time = new_start
                        entry.end_time = new_end
                        entry.activity = activity
                        entry.availability = availability
                        entry.save()

                    except (ValueError, TypeError):
                        error_message = "Ошибка: Укажите корректное время в формате ЧЧ:ММ."
                        break

            elif action == 'add':
                new_activity = request.POST.get('new_activity')
                new_availability = request.POST.get('new_availability')
                new_start_time = request.POST.get('new_start_time')
                new_end_time = request.POST.get('new_end_time')

                if new_activity and new_availability and new_start_time and new_end_time:
                    try:
                        start_time = datetime.strptime(new_start_time, "%H:%M").time()
                        end_time = datetime.strptime(new_end_time, "%H:%M").time()

                        if start_time >= end_time:
                            error_message = "Время начала должно быть раньше времени окончания."
                        elif start_time < WORK_START or end_time > WORK_END:
                            error_message = "Рабочее время должно быть в диапазоне с 09:00 до 18:00."
                        elif has_time_overlap(start_time, end_time, entries):
                            error_message = "В расписании есть ошибка, связанная с пересечением времени."
                        else:
                            ScheduleTemplate.objects.create(
                                user=user,
                                week_type=week_str,
                                day=selected_day,
                                activity=new_activity,
                                availability=new_availability,
                                start_time=start_time,
                                end_time=end_time
                            )
                            return redirect(f"{request.path}?week={selected_week}&day={selected_day}")
                    except ValueError:
                        error_message = "Ошибка: Укажите корректное время в формате ЧЧ:ММ."
                else:
                    error_message = "Пожалуйста, заполните все поля для добавления."

    # Добавим визуальное расписание
    hours = list(range(9, 18))
    schedule_blocks = []

    if selected_day is not None and selected_week is not None:
        today = localdate()
        start_of_week = today - timedelta(days=today.weekday())
        if selected_week == 2:
            start_of_week += timedelta(weeks=1)

        current_date = start_of_week + timedelta(days=selected_day)
        schedule_blocks = build_schedule_blocks(entries, current_date)

    return render(request, 'schedule/edit_template_schedule.html', {
        'selected_week': selected_week,
        'selected_day': selected_day,
        'entries': entries,
        'error_message': error_message,
        'days': DAYS_OF_WEEK,
        'new_activity': new_activity,
        'new_availability': new_availability,
        'new_start_time': new_start_time,
        'new_end_time': new_end_time,
        'hours': hours,
        'schedule_blocks': schedule_blocks,
        'schedule_mode': schedule_mode,
    })

@never_cache
@login_required
def edit_operational_schedule(request):
    user = request.user
    date_str = request.GET.get('date') or request.POST.get('selected_date')
    error_message = None

    try:
        selected_date = parse_date(date_str)
        if selected_date is None:
            raise ValueError
    except (ValueError, TypeError):
        selected_date = localdate()

    op_entries = OperationalSchedule.objects.filter(user=user, date=selected_date)
    weekday = selected_date.weekday()
    week_type = get_week_type(user, selected_date)
    tmpl_entries = ScheduleTemplate.objects.filter(user=user, day=weekday, week_type=week_type)

    if request.method == 'POST':
        action = request.POST.get('action')

        if action and action.startswith('delete_'):
            try:
                entry_id = int(action.replace('delete_', ''))
                OperationalSchedule.objects.get(id=entry_id, user=user).delete()
                return redirect(f"{request.path}?date={selected_date}")
            except (ValueError, OperationalSchedule.DoesNotExist):
                error_message = "Не удалось удалить запись."

        elif action == 'save':
            for entry in op_entries:
                activity = request.POST.get(f'activity_{entry.id}')
                availability = request.POST.get(f'availability_{entry.id}')
                start_time = request.POST.get(f'start_time_{entry.id}')
                end_time = request.POST.get(f'end_time_{entry.id}')

                try:
                    new_start = datetime.strptime(start_time, "%H:%M").time()
                    new_end = datetime.strptime(end_time, "%H:%M").time()

                    if new_start >= new_end:
                        error_message = "Время начала должно быть раньше окончания."
                        break
                    if new_start < WORK_START or new_end > WORK_END:
                        error_message = "Рабочее время должно быть в диапазоне с 09:00 до 18:00."
                        break
                    if has_time_overlap(new_start, new_end, op_entries, exclude_id=entry.id):
                        error_message = "Обнаружено пересечение по времени."
                        break

                    entry.start_time = new_start
                    entry.end_time = new_end
                    entry.activity = activity
                    entry.availability = availability
                    entry.save()

                except Exception:
                    error_message = "Ошибка при обновлении записи."
                    break

        elif action == 'add':
            new_activity = request.POST.get('new_activity')
            new_availability = request.POST.get('new_availability')
            new_start = request.POST.get('new_start_time')
            new_end = request.POST.get('new_end_time')

            if new_activity and new_availability and new_start and new_end:
                try:
                    start_time = datetime.strptime(new_start, "%H:%M").time()
                    end_time = datetime.strptime(new_end, "%H:%M").time()

                    if start_time >= end_time:
                        error_message = "Неверный интервал времени."
                    elif has_time_overlap(start_time, end_time, op_entries):
                        error_message = "Обнаружено пересечение по времени."
                    else:
                        OperationalSchedule.objects.create(
                            user=user,
                            date=selected_date,
                            activity=new_activity,
                            availability=new_availability,
                            start_time=start_time,
                            end_time=end_time
                        )
                        return redirect(f"{request.path}?date={selected_date}")
                except Exception:
                    error_message = "Ошибка при добавлении новой записи."
            else:
                error_message = "Заполните все поля для добавления."

    operational_with_source = []
    for entry in op_entries:
        entry.source = 'operational'
        operational_with_source.append(entry)

    combined_entries = list(op_entries) + [
        type('Entry', (), {
            'activity': t.activity,
            'availability': t.availability,
            'start_time': s,
            'end_time': e,
            'source': 'template'
        })
        for t in tmpl_entries
        for s, e in subtract_intervals(t, op_entries)
    ]

    schedule_blocks = build_schedule_blocks(combined_entries, selected_date)

    return render(request, 'schedule/edit_operational_schedule.html', {
        'selected_date': selected_date,
        'entries': op_entries,
        'error_message': error_message,
        'hours': list(range(9, 18)),
        'schedule_blocks': schedule_blocks,
        'days': DAYS_OF_WEEK,
    })

