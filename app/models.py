import django
from django.contrib.auth.models import User
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone

_CHECK_KWARG = 'condition' if django.VERSION >= (5, 1) else 'check'


class Role(models.TextChoices):
    DEVELOPER = 'developer', 'Разработчик'
    EXPERT = 'expert', 'Эксперт'
    ADMIN = 'admin', 'Администратор'


class Profile(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='profile',
        verbose_name='Пользователь',
    )
    full_name = models.CharField('ФИО', max_length=255)
    age = models.PositiveIntegerField('Возраст', null=True, blank=True)
    role = models.CharField(
        'Роль',
        max_length=20,
        choices=Role.choices,
        default=Role.DEVELOPER,
    )

    class Meta:
        verbose_name = 'Профиль'
        verbose_name_plural = 'Профили'

    def __str__(self):
        return self.full_name


class Nomination(models.Model):
    title = models.CharField('Название', max_length=255)
    criteria = models.TextField('Критерии')
    created_at = models.DateTimeField('Создана', auto_now_add=True)

    class Meta:
        verbose_name = 'Номинация'
        verbose_name_plural = 'Номинации'

    def __str__(self):
        return self.title


class Project(models.Model):
    owner = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='project',
        verbose_name='Разработчик',
    )
    title = models.CharField('Название', max_length=255)
    description = models.TextField('Описание')
    locked = models.BooleanField('Заблокирован', default=False)
    created_at = models.DateTimeField('Добавлен', auto_now_add=True)

    class Meta:
        verbose_name = 'Проект'
        verbose_name_plural = 'Проекты'

    def __str__(self):
        return self.title


class VotingState(models.Model):
    class Phase(models.TextChoices):
        PREPARATION = 'preparation', 'Подготовка'
        VOTING = 'voting', 'Голосование'
        FINISHED = 'finished', 'Завершено'

    current_project = models.ForeignKey(
        Project,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
        verbose_name='Проект, за который идёт голосование',
    )
    pending_project = models.ForeignKey(
        Project,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
        verbose_name='Ожидающий проект',
    )
    switch_deadline = models.DateTimeField(
        'Дедлайн переключения',
        null=True,
        blank=True,
    )
    phase = models.CharField(
        'Фаза',
        max_length=20,
        choices=Phase.choices,
        default=Phase.PREPARATION,
    )

    class Meta:
        verbose_name = 'Состояние голосования'
        verbose_name_plural = 'Состояния голосования'

    def __str__(self):
        return f'{self.get_phase_display()} — {self.current_project or "проект не выбран"}'

    def apply_pending_if_expired(self):
        if (
            self.pending_project is not None
            and self.switch_deadline is not None
            and timezone.now() >= self.switch_deadline
        ):
            self.current_project = self.pending_project
            self.pending_project = None
            self.switch_deadline = None
            self.save()

    @classmethod
    def load(cls):
        state, _ = cls.objects.get_or_create(id=1)
        return state


class ProjectScreenshot(models.Model):
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name='screenshots',
        verbose_name='Проект',
    )
    image = models.ImageField('Скриншот', upload_to='projects/screenshots/')
    uploaded_at = models.DateTimeField('Загружен', auto_now_add=True)

    class Meta:
        verbose_name = 'Скриншот'
        verbose_name_plural = 'Скриншоты'

    def __str__(self):
        return f'{self.project} — {self.id}'


class Vote(models.Model):
    nomination = models.ForeignKey(
        Nomination,
        on_delete=models.CASCADE,
        related_name='votes',
        verbose_name='Номинация',
        null=True,
        blank=True,
    )
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name='votes',
        verbose_name='Проект',
    )
    voter = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='votes',
        verbose_name='Голосующий',
    )
    score_technical = models.PositiveSmallIntegerField(
        'Техническая реализация',
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
    )
    score_aesthetics = models.PositiveSmallIntegerField(
        'Эстетичность',
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
    )
    score_playability = models.PositiveSmallIntegerField(
        'Играбельность',
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
    )
    created_at = models.DateTimeField('Создан', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлён', auto_now=True)

    class Meta:
        verbose_name = 'Голос'
        verbose_name_plural = 'Голоса'
        constraints = [
            models.UniqueConstraint(
                fields=['voter', 'project'],
                name='one_vote_per_user_project',
            ),
            models.CheckConstraint(
                **{_CHECK_KWARG: (
                    Q(
                        score_technical__isnull=True,
                        score_aesthetics__isnull=True,
                        score_playability__isnull=True,
                    )
                    | Q(
                        score_technical__isnull=False,
                        score_aesthetics__isnull=False,
                        score_playability__isnull=False,
                    )
                ), 'name': 'scores_all_or_none'},
            ),
        ]

    def __str__(self):
        nom = self.nomination or 'Без номинации'
        return f'{self.voter} → {self.project} ({nom})'
