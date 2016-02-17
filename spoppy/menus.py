import logging

from .responses import UP, QUIT
from .util import format_track

logger = logging.getLogger(__name__)


class Options(dict):
    def match_best_or_none(self, pattern):
        logger.debug('Trying to match %s' % pattern)
        pattern = pattern.lower()
        if pattern in self:
            return self[pattern][1]
        possibilities_key = []
        possibilities_name = []
        for key, (name, destination) in self.items():
            if pattern == key.lstrip(' '):
                return self[key][1]
            if key.startswith(pattern):
                possibilities_key.append(key)
            if pattern in name.lower():
                possibilities_name.append(key)
        logger.debug('possibilities_key: %s' % possibilities_key)
        logger.debug('possibilities_name: %s' % possibilities_name)
        if possibilities_key:
            if len(possibilities_key) == 1:
                return self[possibilities_key[0]][1]
        elif possibilities_name:
            if len(possibilities_name) == 1:
                return self[possibilities_name[0]][1]


class Menu(object):
    GLOBAL_OPTIONS = Options({
        'u': ('..', UP),
        'q': ('quit', QUIT)
    })
    INCLUDE_UP_ITEM = True

    def __init__(self, navigator):
        self.navigator = navigator

    def initialize(self):
        self._options = Options(self.get_options())

    def get_response(self):
        response = None
        while not response:
            response = self.is_valid_response(input('>>> '))
            if response == 'u' and not self.INCLUDE_UP_ITEM:
                response = None
        logger.debug('Got response %s' % response)
        return response

    def is_valid_response(self, response):
        return (
            self.GLOBAL_OPTIONS.match_best_or_none(response) or
            self._options.match_best_or_none(response)
        )

    def get_ui(self):
        menu_items = tuple(
            self.get_menu_item(key, value[0]) for key, value in
            sorted(self._options.items()) + list(self.GLOBAL_OPTIONS.items())
            if self.INCLUDE_UP_ITEM or key != 'u'
        )
        above_menu_items = self.get_header()
        return '\n'.join((above_menu_items, '') + menu_items)

    def get_menu_item(self, key, value):
        return '[%s]: %s' % (key, value)

    def get_header(self):
        return ''


class LiveMenu(Menu):
    pass


class MainMenu(Menu):
    INCLUDE_UP_ITEM = False

    def get_options(self):
        return {
            'p': ('View playlists', PlayListOverview(self.navigator))
        }


class PlayListOverview(Menu):

    def get_options(self):
        results = {}
        playlists = self.navigator.session.playlist_container
        playlists = enumerate(
            sorted(
                (
                    playlist for playlist in playlists
                    if playlist.name and hasattr(playlist, 'link')
                ),
                key=lambda x: x.name
            )
        )
        for i, playlist in playlists:
            menu_item = PlayListSelected(self.navigator)
            menu_item.playlist = playlist.link.as_playlist()
            results[str(i+1).rjust(4)] = (menu_item.playlist.name, menu_item)
        return results

    def get_header(self):
        return 'Select a playlist'


class PlayListSelected(Menu):

    def shuffle_play(self):
        self.navigator.player.load_playlist(
            self.playlist,
            shuffle=True
        )
        self.navigator.player.play_current_song()
        return self.navigator.player

    def select_song(self, track_idx):
        def song_selected():
            self.navigator.player.load_playlist(
                self.playlist,
            )
            self.navigator.player.play_track(track_idx)
            return self.navigator.player
        return song_selected

    def get_options(self):
        results = {}
        results['sp'] = ('Shuffle play', self.shuffle_play)
        for i, track in enumerate(self.playlist.tracks):
            results[str(i+1).rjust(4)] = (
                format_track(track), self.select_song(i)
            )

        return results

    def get_header(self):
        return 'Playlist [%s] selected' % self.playlist.name