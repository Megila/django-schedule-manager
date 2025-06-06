from django.db import models
from django.contrib.auth.models import User
from phonenumber_field.modelfields import PhoneNumberField
from django.utils.translation import gettext_lazy as _


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, verbose_name=_("Пользователь"))
    phone_number = PhoneNumberField(region='RU', null=True, blank=True, verbose_name=_("Телефон"))

    class ScheduleMode(models.TextChoices):
        ONE = 'one', _('Одна неделя')
        TWO = 'two', _('Две недели')

    schedule_mode = models.CharField(
        max_length=10,
        choices=ScheduleMode.choices,
        default=ScheduleMode.ONE,
        verbose_name=_("Режим расписания")
    )

    class Meta:
        verbose_name = _("Профиль пользователя")
        verbose_name_plural = _("Профили пользователей")

    def __str__(self):
        return f'Профиль {self.user.username}'


class ScheduleTemplate(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name=_("Пользователь"))

    class WeekType(models.TextChoices):
        ONE = 'one', _('Одна неделя')
        TWO = 'two', _('Две недели')

    week_type = models.CharField(max_length=10, choices=WeekType.choices, verbose_name=_("Тип недели"))
    day = models.IntegerField(verbose_name=_("День недели"))  # 0=Monday, ..., 6=Sunday
    activity = models.CharField(max_length=100, verbose_name=_("Занятость"))
    availability = models.CharField(max_length=100, verbose_name=_("Доступность"))
    start_time = models.TimeField(verbose_name=_("Начало"))
    end_time = models.TimeField(verbose_name=_("Конец"))

    class Meta:
        verbose_name = _("Шаблон расписания")
        verbose_name_plural = _("Шаблоны расписания")


class OperationalSchedule(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name=_("Пользователь"))
    date = models.DateField(verbose_name=_("Дата"))
    activity = models.CharField(max_length=100, verbose_name=_("Занятость"))
    availability = models.CharField(max_length=100, verbose_name=_("Доступность"))
    start_time = models.TimeField(verbose_name=_("Начало"))
    end_time = models.TimeField(verbose_name=_("Конец"))

    class Meta:
        verbose_name = _("Рабочее расписание")
        verbose_name_plural = _("Рабочие расписания")


class Project(models.Model):
    name = models.CharField(max_length=100, verbose_name=_("Название проекта"))
    users = models.ManyToManyField(User, related_name='projects', verbose_name=_("Пользователи"))

    class Meta:
        verbose_name = _("Проект")
        verbose_name_plural = _("Проекты")

    def __str__(self):
        return self.name
