"""
python manage.py seed_spaces

Seeds the 4 core Spaces. Safe to re-run — uses get_or_create on slug.
"""

from django.core.management.base import BaseCommand
from spaces.models import Space


SPACES = [
    {
        'slug':        'philosophy',
        'title':       'Deep Philosophy',
        'tagline':     'Exploring consciousness, meaning, and human existence.',
        'description': (
            'Deep Philosophy is a premium intellectual Realm dedicated to the '
            'most fundamental questions about reality, consciousness, ethics, and '
            'the human condition. Members gather here to exchange ideas, debate '
            'timeless questions, and listen to leading voices in philosophy. '
            'This is a place for depth, not noise — where curiosity is the only '
            'prerequisite and every perspective is examined with rigour.'
        ),
        'emoji':        '🏛',
        'atmosphere':   'philosophy',
        'accent_color': '#C9A84C',
    },
    {
        'slug':        'ai-research',
        'title':       'AI Research',
        'tagline':     'Mapping the frontier of machine cognition.',
        'description': (
            'AI Research is a high-signal Realm for researchers, engineers, and '
            'curious minds tracking the frontier of artificial intelligence. '
            'Discussions range from cutting-edge papers and alignment debates to '
            'the philosophical implications of machine cognition. SuperHosts run '
            'weekly deep-dives and live paper discussions open to all members.'
        ),
        'emoji':        '🧠',
        'atmosphere':   'ai_research',
        'accent_color': '#3AB8E0',
    },
    {
        'slug':        'deep-cosmos',
        'title':       'Deep Cosmos',
        'tagline':     'The infinite dark, held in focused inquiry.',
        'description': (
            'Deep Cosmos brings together astrophysicists, science communicators, '
            'and the endlessly curious to explore the universe — from quantum '
            'mechanics to cosmology, dark matter to the Fermi paradox. Whether '
            'you have a PhD or just a hunger to understand the cosmos, this Realm '
            'is your home.'
        ),
        'emoji':        '🌌',
        'atmosphere':   'deep_science',
        'accent_color': '#6A9EFF',
    },
    {
        'slug':        'psychology',
        'title':       'Psychology',
        'tagline':     'Understanding the architecture of the self.',
        'description': (
            'Psychology dives into the mind — from clinical research and '
            'neuroscience to everyday mental models and the psychology of '
            'decision-making. Members share insights, challenge assumptions, '
            'and explore what it means to live a more examined, intentional life. '
            'Open to practitioners, students, and the self-aware alike.'
        ),
        'emoji':        '🪞',
        'atmosphere':   'psychology',
        'accent_color': '#E067A0',
    },
]


class Command(BaseCommand):
    help = 'Seed the 4 core Spaces into the database'

    def handle(self, *args, **options):
        created_count = 0
        for data in SPACES:
            space, created = Space.objects.get_or_create(
                slug=data['slug'],
                defaults={k: v for k, v in data.items() if k != 'slug'},
            )
            status = 'created' if created else 'already exists'
            self.stdout.write(f"  {data['emoji']} {data['title']} ({data['slug']}) — {status}")
            if created:
                created_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'\nDone. {created_count} new space(s) created, '
                f'{len(SPACES) - created_count} already existed.'
            )
        )
