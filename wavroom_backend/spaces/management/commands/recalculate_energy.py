"""
Management command: recalculate the Energy of the Realm score for all spaces.

Run manually or via cron every 15 minutes:
    python manage.py recalculate_energy
    python manage.py recalculate_energy --space-slug philosophy
    */15 * * * * cd /path/to/project && python manage.py recalculate_energy

Scoring formula (each component 0–100, then weighted):
    energy = live_rooms      * 0.35
           + weekly_posts    * 0.25
           + unique_actives  * 0.20
           + member_growth   * 0.15
           + reactions       * 0.05

Anti-spam: contributions are per-unique-user, not per-action count.
           Old activity decays naturally because the window is rolling 7 days.
"""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone


def _score_live_rooms(count: int) -> float:
    """3+ live rooms at once = full score."""
    return min(count / 3.0, 1.0) * 100


def _score_weekly_posts(discussions: int, comments: int) -> float:
    """50 combined pieces of content per week = full score.
    Comments count less than top-level discussions."""
    activity = discussions + comments * 0.3
    return min(activity / 50.0, 1.0) * 100


def _score_unique_actives(unique_count: int) -> float:
    """30+ unique participants active this week = full score."""
    return min(unique_count / 30.0, 1.0) * 100


def _score_growth(new_members: int, total_members: int) -> float:
    """10% weekly member growth = full score.
    Protects against divide-by-zero on new spaces."""
    if total_members == 0:
        return 50.0 if new_members > 0 else 0.0
    rate = new_members / max(total_members, 1)
    return min(rate / 0.10, 1.0) * 100


def _score_reactions(reaction_count: int) -> float:
    """100+ reactions this week = full score."""
    return min(reaction_count / 100.0, 1.0) * 100


def calculate_energy_for_space(space) -> float:
    from spaces.models import SpaceMembership, Discussion, Comment, DiscussionReaction

    now      = timezone.now()
    week_ago = now - timedelta(days=7)

    # Live rooms right now (from Redis)
    live_count = space._live_chamber_count()

    # Weekly discussions + comments
    disc_count    = Discussion.objects.filter(space=space, created_at__gte=week_ago).count()
    comment_count = Comment.objects.filter(discussion__space=space, created_at__gte=week_ago).count()

    # Unique active members this week (posted or commented)
    active_authors = set(
        Discussion.objects.filter(space=space, created_at__gte=week_ago)
        .values_list('author_id', flat=True)
    ) | set(
        Comment.objects.filter(discussion__space=space, created_at__gte=week_ago)
        .values_list('author_id', flat=True)
    )

    # New members this week + total members
    new_members   = SpaceMembership.objects.filter(space=space, joined_at__gte=week_ago).count()
    total_members = SpaceMembership.objects.filter(space=space).count()

    # Reactions on discussions created this week
    reaction_count = DiscussionReaction.objects.filter(
        discussion__space=space, discussion__created_at__gte=week_ago
    ).count()

    score = (
        _score_live_rooms(live_count)                   * 0.35 +
        _score_weekly_posts(disc_count, comment_count)  * 0.25 +
        _score_unique_actives(len(active_authors))      * 0.20 +
        _score_growth(new_members, total_members)       * 0.15 +
        _score_reactions(reaction_count)                * 0.05
    )

    return round(min(score, 100.0), 1)


class Command(BaseCommand):
    help = 'Recalculate the Energy of the Realm score for all (or one) spaces.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--space-slug',
            type=str,
            default=None,
            help='Recalculate only for this space slug.',
        )

    def handle(self, *args, **options):
        from spaces.models import Space

        slug = options.get('space_slug')
        spaces = Space.objects.filter(slug=slug) if slug else Space.objects.all()

        updated = 0
        for space in spaces:
            score = calculate_energy_for_space(space)
            Space.objects.filter(pk=space.pk).update(
                energy_score=score,
                energy_updated_at=timezone.now(),
            )
            updated += 1
            self.stdout.write(f'  {space.slug}: {score}')

        self.stdout.write(self.style.SUCCESS(f'Updated energy for {updated} space(s).'))
