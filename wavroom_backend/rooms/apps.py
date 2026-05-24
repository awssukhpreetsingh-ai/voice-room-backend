import os
import threading
import time

from django.apps import AppConfig

_reaper_started = False


def _run_reaper():
    # Imported here to avoid touching Django models before setup is complete.
    from rooms import redis_client as rc
    while True:
        time.sleep(60)
        try:
            rc.prune_expired()
        except Exception as e:
            print(f'[reaper] error: {e}')


class RoomsConfig(AppConfig):
    name = 'rooms'

    def ready(self):
        global _reaper_started
        if _reaper_started:
            return
        _reaper_started = True
        t = threading.Thread(target=_run_reaper, daemon=True, name='room-reaper')
        t.start()
        print('[reaper] background room reaper started')
