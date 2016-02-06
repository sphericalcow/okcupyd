from . import util
from . import helpers
from .xpath import xpb


class Essays(object):
    """Interface to reading and writing essays."""

    @staticmethod
    def build_essay_property(essay_title, essay_index, essay_name):
        titles_xpb = xpb.div.with_classes("essays2015-essay-title","profilesection-title")
        texts_xpb = xpb.div.with_class("essays2015-essay-content")
        @property
        def essay(self):
            for title_element, text_element in zip(titles_xpb.apply_(self._profile.profile_tree),
                                                   texts_xpb.apply_(self._profile.profile_tree)):
                if helpers.replace_chars(title_element.text_content()).strip() == essay_title:
                    return text_element.text_content().strip()
            return None

        @essay.setter
        def set_essay_text(self, essay_text):
            self._submit_essay(essay_index, essay_text)

        return set_essay_text

    @classmethod
    def _init_essay_properties(cls):
        for essay_title, (essay_index, essay_name) in cls.essay_names.iteritems():
            setattr(cls, essay_name,
                    cls.build_essay_property(essay_title, essay_index, essay_name))

    _essays_xpb = xpb.div(id='main_column')
    #: A dictionary of the attribute names that are used to store the text of
    #: of essays on instances of this class: key is the title in the
    #: corresponding div on OKC and value is the name used by okcupyd
    essay_names = {'My self-summary' : (0,'self_summary'),
                   "What I'm doing with my life" : (1,'my_life'),
                   "I'm really good at" : (2,'good_at'),
                   'The first things people usually notice about me' : (3,'people_first_notice'),
                   'Favorite books, movies, shows, music, and food' : (4,'favorites'),
                   'The six things I could never do without' : (5,'six_things'),
                   'I spend a lot of time thinking about' : (6,'think_about'),
                   'On a typical Friday night I am' : (7,'friday_night'),
                   "The most private thing I'm willing to admit" : (8,'private_admission'),
                   'You should message me if' : (9,'message_me_if')}

    def __init__(self, profile):
        """:param profile: A :class:`.Profile`"""
        self._profile = profile
        # This used to actually test that indices matched essay names correctly.
        # With the API change at the end of 2015, it became useless.
        self._short_name_to_title = {}
        for essay_title, (essay_index, essay_name) in self.essay_names.iteritems():
            self._short_name_to_title[essay_name] = essay_title

    @property
    def short_name_to_title(self):
        for i in self: pass # Make sure that all essays names have been retrieved
        return self._short_name_to_title

    @util.cached_property
    def _essays(self):
        return self._essays_xpb.one_(self._profile.profile_tree)

    def _submit_essay(self, essay_id, essay_body):
        self._profile.authcode_post('profileedit2', data={
            "essay_id": essay_id,
            "essay_body": essay_body,
            "okc_api": 1
        })
        self.refresh()

    def refresh(self):
        self._profile.refresh()
        util.cached_property.bust_caches(self)

    def __iter__(self):
        for essay_index, essay_name in sorted(self.essay_names.values()):
            yield getattr(self, essay_name)


Essays._init_essay_properties()
