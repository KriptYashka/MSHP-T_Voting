from django import forms
from django.contrib.auth.models import User

from .models import Role


class UserCreateForm(forms.Form):
    username = forms.CharField(label='Логин', max_length=150)
    password = forms.CharField(label='Пароль', widget=forms.PasswordInput)
    full_name = forms.CharField(label='ФИО', max_length=255)
    age = forms.IntegerField(label='Возраст', min_value=1, max_value=150, required=False)
    role = forms.ChoiceField(label='Роль', choices=Role.choices)

    def clean_username(self):
        username = self.cleaned_data['username']
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError('Пользователь с таким логином уже существует')
        return username


class UserEditForm(forms.Form):
    user_id = forms.IntegerField(widget=forms.HiddenInput)
    full_name = forms.CharField(
        label='ФИО', max_length=255,
        widget=forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
    )
    age = forms.IntegerField(
        label='Возраст', min_value=1, max_value=150, required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control form-control-sm'}),
    )
    role = forms.ChoiceField(
        label='Роль', choices=Role.choices,
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'}),
    )
    password = forms.CharField(
        label='Новый пароль',
        widget=forms.PasswordInput(attrs={'class': 'form-control form-control-sm'}),
        required=False,
        help_text='Оставьте пустым, чтобы не менять',
    )


class NominationCreateForm(forms.Form):
    title = forms.CharField(label='Название', max_length=255)
    criteria = forms.CharField(label='Критерии', widget=forms.Textarea)


class ProjectCreateForm(forms.Form):
    owner = forms.ModelChoiceField(
        label='Разработчик',
        queryset=User.objects.none(),
    )
    title = forms.CharField(label='Название', max_length=255)
    description = forms.CharField(label='Описание', widget=forms.Textarea)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['owner'].queryset = User.objects.filter(
            profile__role=Role.DEVELOPER,
        ).exclude(project__isnull=False)
