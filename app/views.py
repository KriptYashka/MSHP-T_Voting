from datetime import timedelta
from functools import wraps

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.middleware.csrf import get_token
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .consumers import broadcast_voting
from .forms import (
    NominationCreateForm, ProfilePasswordForm, ProjectCreateForm,
    UserCreateForm, UserEditForm,
)
from .models import (
    Nomination, Profile, Project, ProjectScreenshot, Role, Vote, VotingState,
)
from .state import build_nomination_results_admin, build_nomination_ranking, build_overall_ranking, get_state_dict


def get_role(user):
    if not user.is_authenticated:
        return None
    profile = getattr(user, 'profile', None)
    if profile is not None:
        return profile.role
    return Role.ADMIN if user.is_superuser else None


def admin_required(view):
    @wraps(view)
    @login_required
    def wrapper(request, *args, **kwargs):
        if get_role(request.user) != Role.ADMIN:
            raise PermissionDenied
        return view(request, *args, **kwargs)
    return wrapper


def jury_required(view):
    @wraps(view)
    @login_required
    def wrapper(request, *args, **kwargs):
        if get_role(request.user) not in (Role.EXPERT, Role.ADMIN):
            raise PermissionDenied
        return view(request, *args, **kwargs)
    return wrapper


def index_page(request):
    return redirect('projects')


def login_page(request):
    if request.user.is_authenticated:
        return redirect('projects')

    if request.method == 'POST':
        username = request.POST.get('username', '')
        password = request.POST.get('password', '')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            next_url = request.POST.get('next') or 'projects'
            return redirect(next_url)
        messages.error(request, 'Неверный логин или пароль')
    return render(request, 'pages/login.html', {'next': request.GET.get('next', '')})


def logout_page(request):
    logout(request)
    return redirect('login')


@login_required
def profile_page(request):
    user = request.user
    profile = getattr(user, 'profile', None)

    if request.method == 'POST':
        form = ProfilePasswordForm(request.POST)
        if form.is_valid():
            user.set_password(form.cleaned_data['new_password'])
            user.save()
            login(request, user)
            messages.success(request, 'Пароль успешно изменён')
            return redirect('profile')
    else:
        form = ProfilePasswordForm()

    return render(request, 'pages/profile.html', {
        'profile': profile,
        'form': form,
    })


@login_required
def projects_list(request):
    own_project = getattr(request.user, 'project', None)
    other_projects = Project.objects.select_related('owner__profile').exclude(
        owner=request.user,
    )

    vs = VotingState.load()
    vs.apply_pending_if_expired()
    active_project = None
    if vs.phase == VotingState.Phase.VOTING and vs.current_project:
        active_project = vs.current_project

    return render(request, 'pages/projects.html', {
        'own_project': own_project,
        'projects': other_projects,
        'active_project': active_project,
    })


@login_required
def project_detail(request, project_id):
    project = get_object_or_404(
        Project.objects.select_related('owner__profile'),
        id=project_id,
    )
    role = get_role(request.user)
    is_owner = hasattr(request.user, 'project') and request.user.project.id == project.id
    can_upload = role == Role.ADMIN or is_owner

    if request.method == 'POST' and can_upload:
        file = request.FILES.get('image')
        if file:
            ProjectScreenshot.objects.create(project=project, image=file)
            messages.success(request, 'Скриншот загружен')
        else:
            messages.error(request, 'Выберите файл')
        return redirect('project_detail', project_id=project.id)

    return render(request, 'pages/project_detail.html', {
        'project': project,
        'can_upload': can_upload,
    })


@login_required
def project_create(request):
    if hasattr(request.user, 'project'):
        messages.error(request, 'У вас уже есть проект')
        return redirect('projects')

    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        description = request.POST.get('description', '').strip()
        if title:
            Project.objects.create(owner=request.user, title=title, description=description)
            messages.success(request, 'Проект создан')
            return redirect('project_detail', project_id=request.user.project.id)
        messages.error(request, 'Название не может быть пустым')

    return render(request, 'pages/project_create.html')


@login_required
def project_edit(request, project_id):
    project = get_object_or_404(Project, id=project_id)
    role = get_role(request.user)
    is_owner = hasattr(request.user, 'project') and request.user.project.id == project.id
    if not (role == Role.ADMIN or is_owner):
        raise PermissionDenied

    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        description = request.POST.get('description', '').strip()
        if title:
            project.title = title
            project.description = description
            project.save()
            messages.success(request, 'Проект обновлён')
        else:
            messages.error(request, 'Название не может быть пустым')
        return redirect('project_detail', project_id=project.id)

    return render(request, 'pages/project_edit.html', {'project': project})


@login_required
def screenshot_delete(request, project_id, screenshot_id):
    project = get_object_or_404(Project, id=project_id)
    role = get_role(request.user)
    is_owner = hasattr(request.user, 'project') and request.user.project.id == project.id
    if not (role == Role.ADMIN or is_owner):
        raise PermissionDenied

    screenshot = get_object_or_404(ProjectScreenshot, id=screenshot_id, project=project)
    if request.method == 'POST':
        screenshot.image.delete(save=False)
        screenshot.delete()
        messages.success(request, 'Скриншот удалён')
    return redirect('project_detail', project_id=project.id)


@login_required
def voting_page(request):
    vs = VotingState.load()
    vs.apply_pending_if_expired()

    if request.method == 'POST':
        project = vs.current_project
        if vs.phase != VotingState.Phase.VOTING or project is None:
            messages.error(request, 'Голосование сейчас не проводится')
        elif project.owner == request.user:
            messages.error(request, 'Нельзя голосовать за свой проект')
        else:
            role = get_role(request.user)
            raw_nom = request.POST.get('nomination_id', '').strip()
            nomination = None
            if raw_nom:
                nomination = Nomination.objects.filter(id=raw_nom).first()

            if role in (Role.EXPERT, Role.ADMIN):
                def parse_score(key):
                    try:
                        value = int(request.POST.get(key, ''))
                    except (TypeError, ValueError):
                        return None
                    return value if 1 <= value <= 10 else None

                scores = {
                    'score_technical': parse_score('score_technical'),
                    'score_aesthetics': parse_score('score_aesthetics'),
                    'score_playability': parse_score('score_playability'),
                }
                if all(v is not None for v in scores.values()):
                    Vote.objects.update_or_create(
                        voter=request.user,
                        project=project,
                        defaults={
                            'nomination': nomination,
                            **scores,
                        },
                    )
                    broadcast_voting()
                else:
                    messages.error(request, 'Оценки по всем трём критериям должны быть от 1 до 10')
            else:
                Vote.objects.update_or_create(
                    voter=request.user,
                    project=project,
                    defaults={
                        'nomination': nomination,
                        'score_technical': None,
                        'score_aesthetics': None,
                        'score_playability': None,
                    },
                )
                broadcast_voting()
        return redirect('voting')

    state = get_state_dict(request.user)
    own_project = getattr(request.user, 'project', None)
    own_project_id = own_project.id if own_project is not None else None
    role = get_role(request.user)
    can_jury = role in (Role.EXPERT, Role.ADMIN)
    can_see_results = can_jury

    return render(request, 'pages/voting.html', {
        'state': state,
        'own_project_id': own_project_id,
        'can_jury': can_jury,
        'can_see_results': can_see_results,
        'csrf_token': get_token(request),
    })


@jury_required
def expert_rate(request):
    projects = Project.objects.select_related('owner__profile').all()
    nominations = Nomination.objects.all()
    own_project = getattr(request.user, 'project', None)

    if request.method == 'POST':
        raw_project = request.POST.get('project_id', '').strip()
        project = Project.objects.filter(id=raw_project).first()
        if project is None:
            messages.error(request, 'Проект не найден')
            return redirect('expert_rate')

        if project.owner == request.user:
            messages.error(request, 'Нельзя оценивать свой проект')
            return redirect('expert_rate')

        raw_nom = request.POST.get('nomination_id', '').strip()
        nomination = None
        if raw_nom:
            nomination = Nomination.objects.filter(id=raw_nom).first()

        def parse_score(key):
            try:
                value = int(request.POST.get(key, ''))
            except (TypeError, ValueError):
                return None
            return value if 1 <= value <= 10 else None

        scores = {
            'score_technical': parse_score('score_technical'),
            'score_aesthetics': parse_score('score_aesthetics'),
            'score_playability': parse_score('score_playability'),
        }
        if all(v is not None for v in scores.values()):
            Vote.objects.update_or_create(
                voter=request.user,
                project=project,
                defaults={
                    'nomination': nomination,
                    **scores,
                },
            )
            messages.success(request, f'Оценка «{project.title}» сохранена')
        else:
            messages.error(request, 'Оценки по всем трём критериям должны быть от 1 до 10')
        return redirect('expert_rate')

    existing_votes = {}
    if request.user.is_authenticated:
        for v in Vote.objects.filter(voter=request.user):
            existing_votes[v.project_id] = {
                'nomination_id': v.nomination_id,
                'score_technical': v.score_technical or '',
                'score_aesthetics': v.score_aesthetics or '',
                'score_playability': v.score_playability or '',
            }

    project_data = []
    for p in projects:
        project_data.append({
            'project': p,
            'vote': existing_votes.get(p.id),
        })

    return render(request, 'pages/expert_rate.html', {
        'project_data': project_data,
        'nominations': nominations,
        'own_project': own_project,
        'scores_range': range(1, 11),
    })


@admin_required
def admin_panel(request):
    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'create_user':
            form = UserCreateForm(request.POST)
            if form.is_valid():
                data = form.cleaned_data
                user = User.objects.create_user(
                    username=data['username'],
                    password=data['password'],
                )
                Profile.objects.create(
                    user=user,
                    full_name=data['full_name'],
                    age=data['age'],
                    role=data['role'],
                )
                messages.success(request, f'Пользователь {data["username"]} создан')
            else:
                messages.error(request, 'Не удалось создать пользователя')

        elif action == 'create_nomination':
            form = NominationCreateForm(request.POST)
            if form.is_valid():
                Nomination.objects.create(**form.cleaned_data)
                messages.success(request, 'Номинация создана')
            else:
                messages.error(request, 'Не удалось создать номинацию')

        elif action == 'create_project':
            form = ProjectCreateForm(request.POST)
            if form.is_valid():
                data = form.cleaned_data
                Project.objects.create(
                    owner=data['owner'],
                    title=data['title'],
                    description=data['description'],
                )
                messages.success(request, 'Проект создан')
            else:
                messages.error(request, 'Не удалось создать проект')

        elif action == 'set_current_project':
            project_id = request.POST.get('project_id')
            project = None
            if project_id:
                project = Project.objects.filter(id=project_id).first()
            state = VotingState.load()
            state.pending_project = project
            state.switch_deadline = timezone.now() + timedelta(seconds=10)
            state.save()
            broadcast_voting()

        elif action == 'set_phase':
            phase = request.POST.get('phase')
            if phase in dict(VotingState.Phase.choices):
                state = VotingState.load()
                state.phase = phase
                state.save()
                broadcast_voting()

        elif action == 'edit_user':
            form = UserEditForm(request.POST)
            if form.is_valid():
                data = form.cleaned_data
                target = User.objects.filter(id=data['user_id']).first()
                if target and hasattr(target, 'profile'):
                    target.profile.full_name = data['full_name']
                    target.profile.age = data['age']
                    target.profile.role = data['role']
                    target.profile.save()
                    if data['password']:
                        target.set_password(data['password'])
                        target.save()
                    messages.success(request, f'Пользователь {target.username} обновлён')
                else:
                    messages.error(request, 'Пользователь не найден')

        return redirect('admin_panel')

    vs = VotingState.load()

    all_users = User.objects.select_related('profile').exclude(is_superuser=True).order_by('username')
    user_edit_forms = []
    for u in all_users:
        if hasattr(u, 'profile'):
            form = UserEditForm(initial={
                'user_id': u.id,
                'full_name': u.profile.full_name,
                'age': u.profile.age,
                'role': u.profile.role,
            })
            user_edit_forms.append((u, form))

    return render(request, 'admin/panel.html', {
        'current_project': vs.current_project,
        'pending_project': vs.pending_project,
        'switch_deadline': vs.switch_deadline,
        'current_phase': vs.phase,
        'nominations': Nomination.objects.all(),
        'projects': Project.objects.select_related('owner__profile').all(),
        'user_form': UserCreateForm(),
        'nomination_form': NominationCreateForm(),
        'project_form': ProjectCreateForm(),
        'phases': VotingState.Phase.choices,
        'user_edit_forms': user_edit_forms,
    })


@admin_required
def admin_results(request):
    nominations = list(Nomination.objects.all())

    tabs = []

    overall_rows = build_overall_ranking()
    tabs.append({
        'nomination': None,
        'label': 'Общий рейтинг',
        'rows': overall_rows,
    })

    for nom in nominations:
        rows = build_nomination_ranking(nom)
        tabs.append({
            'nomination': nom,
            'label': nom.title,
            'rows': rows,
        })

    no_nom_rows = build_nomination_ranking(None)
    tabs.append({
        'nomination': None,
        'label': 'Без номинации',
        'rows': no_nom_rows,
    })

    return render(request, 'admin/results.html', {
        'tabs': tabs,
    })
