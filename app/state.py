from django.db.models import Avg, Count, Q

from .models import Nomination, Project, Vote, VotingState

CRITERIA_FIELDS = [
    ('score_technical', 'technical'),
    ('score_aesthetics', 'aesthetics'),
    ('score_playability', 'playability'),
]


def build_nomination_results(project, nomination):
    if project is None:
        return {'votes_count': 0, 'jury_count': 0}
    qs = project.votes.filter(nomination=nomination)
    votes_count = qs.count()
    jury_count = qs.exclude(score_technical__isnull=True).count()
    return {
        'votes_count': votes_count,
        'jury_count': jury_count,
    }


def build_nomination_results_admin(project, nomination):
    if project is None:
        return {'votes_count': 0, 'jury_count': 0, 'criteria': {}, 'overall': 0}
    qs = project.votes.filter(nomination=nomination)
    votes_count = qs.count()
    jury = list(qs.exclude(score_technical__isnull=True))
    jury_count = len(jury)
    criteria = {}
    for field, key in CRITERIA_FIELDS:
        values = [getattr(vote, field) for vote in jury if getattr(vote, field) is not None]
        criteria[key] = round(sum(values) / len(values), 2) if values else 0
    overall = round(sum(criteria.values()) / len(criteria), 2) if jury_count else 0
    return {
        'votes_count': votes_count,
        'jury_count': jury_count,
        'criteria': criteria,
        'overall': overall,
    }


def build_nomination_ranking(nomination):
    projects = Project.objects.annotate(
        vote_count=Count('votes', filter=Q(votes__nomination=nomination)),
        jury_count=Count(
            'votes',
            filter=Q(votes__nomination=nomination) & Q(votes__score_technical__isnull=False),
        ),
        avg_technical=Avg(
            'votes__score_technical',
            filter=Q(votes__nomination=nomination) & Q(votes__score_technical__isnull=False),
        ),
        avg_aesthetics=Avg(
            'votes__score_aesthetics',
            filter=Q(votes__nomination=nomination) & Q(votes__score_aesthetics__isnull=False),
        ),
        avg_playability=Avg(
            'votes__score_playability',
            filter=Q(votes__nomination=nomination) & Q(votes__score_playability__isnull=False),
        ),
    ).filter(vote_count__gt=0).order_by('-avg_technical', '-avg_aesthetics', '-avg_playability')

    rows = []
    for p in projects:
        criteria = {
            'technical': round(p.avg_technical or 0, 2),
            'aesthetics': round(p.avg_aesthetics or 0, 2),
            'playability': round(p.avg_playability or 0, 2),
        }
        overall = round(
            sum(criteria.values()) / 3, 2
        ) if p.jury_count else 0
        rows.append({
            'project': p,
            'owner': p.owner.profile.full_name if hasattr(p.owner, 'profile') else p.owner.username,
            'votes_count': p.vote_count,
            'jury_count': p.jury_count,
            'criteria': criteria,
            'overall': overall,
        })

    rows.sort(key=lambda r: r['overall'], reverse=True)
    for i, row in enumerate(rows, 1):
        row['rank'] = i

    return rows


def build_overall_ranking():
    projects = Project.objects.annotate(
        vote_count=Count('votes'),
        jury_count=Count('votes', filter=Q(votes__score_technical__isnull=False)),
        avg_technical=Avg('votes__score_technical', filter=Q(votes__score_technical__isnull=False)),
        avg_aesthetics=Avg('votes__score_aesthetics', filter=Q(votes__score_aesthetics__isnull=False)),
        avg_playability=Avg('votes__score_playability', filter=Q(votes__score_playability__isnull=False)),
    ).filter(vote_count__gt=0).order_by('-avg_technical', '-avg_aesthetics', '-avg_playability')

    rows = []
    for p in projects:
        criteria = {
            'technical': round(p.avg_technical or 0, 2),
            'aesthetics': round(p.avg_aesthetics or 0, 2),
            'playability': round(p.avg_playability or 0, 2),
        }
        overall = round(sum(criteria.values()) / 3, 2) if p.jury_count else 0
        rows.append({
            'project': p,
            'owner': p.owner.profile.full_name if hasattr(p.owner, 'profile') else p.owner.username,
            'votes_count': p.vote_count,
            'jury_count': p.jury_count,
            'criteria': criteria,
            'overall': overall,
        })

    rows.sort(key=lambda r: r['overall'], reverse=True)
    for i, row in enumerate(rows, 1):
        row['rank'] = i

    return rows


def get_state_dict(user=None):
    vs = VotingState.load()
    vs.apply_pending_if_expired()
    project = vs.current_project

    project_data = None
    if project:
        project_data = {
            'id': project.id,
            'title': project.title,
            'description': project.description,
            'owner': project.owner.profile.full_name if hasattr(project.owner, 'profile') else project.owner.username,
            'screenshots': [s.image.url for s in project.screenshots.all()],
        }

    my_vote = None
    if project and user is not None and user.is_authenticated:
        vote = Vote.objects.filter(voter=user, project=project).first()
        if vote:
            my_vote = {
                'nomination_id': vote.nomination_id,
            }

    nominations_data = []
    for nom in Nomination.objects.all():
        res = build_nomination_results(project, nom)
        nominations_data.append({
            'id': nom.id,
            'title': nom.title,
            **res,
        })

    no_nom = build_nomination_results(project, None)

    pending_data = None
    if vs.pending_project and vs.switch_deadline:
        pending_data = {
            'project_id': vs.pending_project.id,
            'project_title': vs.pending_project.title,
            'deadline': vs.switch_deadline.isoformat(),
        }

    return {
        'phase': vs.phase,
        'project': project_data,
        'nominations': nominations_data,
        'no_nomination': no_nom,
        'my_vote': my_vote,
        'pending_switch': pending_data,
    }
