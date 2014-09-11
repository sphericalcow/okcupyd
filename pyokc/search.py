import inspect
import logging
import re

from lxml import html
import simplejson

from . import helpers
from . import magicnumbers
from . import objects
from . import util


log = logging.getLogger()


builder_to_keys = {}
builder_to_decider = {}


def any_decider(function, incoming_keys, accepted_keys):
    return bool(set(incoming_keys).intersection(accepted_keys))


def all_decider(function, incoming_keys, accepted_keys):
    return set(accepted_keys).issubset(incoming_keys)


@util.n_partialable
def register_filter_builder(function, keys=(), decider=all_decider):
    function_arguments = inspect.getargspec(function).args
    if keys:
        assert len(keys) == len(function_arguments)
    else:
        keys = function_arguments
    builder_to_keys[function] = keys
    builder_to_decider[function] = decider

    return function


@register_filter_builder
def looking_for_filter(looking_for):
    return '0,{0}'.format(magicnumbers.seeking[looking_for.lower()])


@register_filter_builder(decider=any_decider)
def age_filter(age_min=18, age_max=99):
    if age_min == None:
        age_min = 18
    return '2,{0},{1}'.format(age_min, age_max)


@register_filter_builder(decider=any_decider)
def attractiveness_filter(attractiveness_min, attractiveness_max):
    if attractiveness_min == None:
        attractiveness_min = 0
    if attractiveness_max == None:
        attractiveness_max = 10000
    return '25,{0},{1}'.format(attractiveness_min, attractiveness_max)


@register_filter_builder(decider=any_decider)
def height_filter(height_min, height_max):
    return magicnumbers.get_height_query(height_min, height_max)


@register_filter_builder
def last_online_filter(last_online):
    return '5,{0}'.format(helpers.format_last_online(last_online))


@register_filter_builder
def status_filter(status):
    return '35,{0}'.format(helpers.format_status(status))


@register_filter_builder
def location_filter(radius):
    return '3,{0}'.format(radius)


for key in ['smokes', 'drinks', 'drugs', 'education', 'job',
            'income', 'religion', 'monogamy', 'diet', 'sign',
            'ethnicity']:
    @register_filter_builder(keys=(key,))
    @util.makelist_decorator
    def option_filter(value):
        magicnumbers.get_options_query(key, [value])


for key, function in [('pets', util.makelist_decorator(magicnumbers.get_pet_queries)),
                      ('offspring', util.makelist_decorator(magicnumbers.get_kids_query)),
                      ('join_date', magicnumbers.get_join_date_query),
                      ('languages', magicnumbers.get_language_query)]:

    register_filter_builder(keys=(key,))(function)


class SearchExecutor(object):
    """
    Search OKCupid profiles, return a list of matching profiles.
    See the search page on OKCupid for a better idea of the
    arguments expected.
    Parameters
    ----------
    location : string, optional
        Location of profiles returned. Accept ZIP codes, city
        names, city & state combinations, and city & country
        combinations. Default to user location if unable to
        understand the string or if no value is given.
    radius : int, optional
        Radius in miles searched, centered on the location.
    number : int, optional
        Number of profiles returned. Default to 18, which is the
        same number that OKCupid returns by default.
    age_min : int, optional
        Minimum age of profiles returned. Cannot be lower than 18.
    age_max : int, optional
        Maximum age of profiles returned. Cannot be higher than 99.
    order_by : str, optional
        Order in which profiles are returned.
    last_online : str, optional
        How recently online the profiles returned are. Can also be
        an int that represents seconds.
    status : str, optional
        Dating status of profiles returned. Default to 'single'
        unless the argument is either 'not single', 'married', or
        'any'.
    height_min : int, optional
        Minimum height in inches of profiles returned.
    height_max : int, optional
        Maximum height in inches of profiles returned.
    looking_for : str, optional
        Describe the gender and orientation of profiles returned.
        If left blank, return some variation of "guys/girls who
        like guys/girls" or "both who like bi girls/guys, depending
        on the user's gender and orientation.
    smokes : str or list of str, optional
        Smoking habits of profiles returned.
    drinks : str or list of str, optional
        Drinking habits of profiles returned.
    drugs : str or list of str, optional
        Drug habits of profiles returned.
    education : str or list of str, optional
        Highest level of education attained by profiles returned.
    job : str or list of str, optional
        Industry in which the profile users work.
    income : str or list of str, optional
        Income range of profiles returned.
    religion : str or list of str, optional
        Religion of profiles returned.
    monogamy : str or list of str, optional
        Whether the profiles returned are monogamous or non-monogamous.
    offspring : str or list of str, optional
        Whether the profiles returned have or want children.
    pets : str or list of str, optional
        Dog/cat ownership of profiles returned.
    languages : str or list of str, optional
        Languages spoken for profiles returned.
    diet : str or list of str, optional
        Dietary restrictions of profiles returned.
    sign : str or list of str, optional
        Astrological sign of profiles returned.
    ethnicity : str or list of str, optional
        Ethnicity of profiles returned.
    join_date : int or str, optional
        Either a string describing the profile join dates ('last
        week', 'last year' etc.) or an int indicating the number
        of maximum seconds from the moment of joining OKCupid.
    keywords : str, optional
        Keywords that the profiles returned must contain. Note that
        spaces separate keywords, ie. `keywords="love cats"` will
        return profiles that contain both "love" and "cats" rather
        than the exact string "love cats".
    """

    def __init__(self, **kwargs):
        self._options = kwargs

    @property
    def location(self):
        return self._options.get('location', '')

    @property
    def gender(self):
        return self._options.get('gender', 'm')

    @property
    def keywords(self):
        return self._options.get('keywords')

    @property
    def order_by(self):
        return self._options.get('order_by', 'match').upper()

    @property
    def filters(self):
        incoming_keys = tuple(self._options.keys())
        builders = [builder for builder, decider in builder_to_decider.items()
                    if decider(builder, incoming_keys, builder_to_keys[builder])]
        return [builder(*[self._options.get(key) for key in builder_to_keys[builder]])
                for builder in builders]

    def set_options(self, **kwargs):
        self.options.update(kwargs)
        return self.options

    def build_search_parameters(self, session, count=9):
        search_parameters = {
            'timekey': 1,
            'matchOrderBy': self.order_by.upper(),
            'custom_search': '0',
            'fromWhoOnline': '0',
            'mygender': self.gender,
            'update_prefs': '1',
            'sort_type': '0',
            'sa': '1',
            'count': str(count),
            'locid': str(helpers.get_locid(session, self.location)),
            'ajax_load': 1,
            'discard_prefs': 1,
            'match_card_class': 'just_appended'
        }
        if self.keywords: search_parameters['keywords'] = self.keywords
        for filter_number, filter_string in enumerate(self.filters, 1):
            search_parameters['filter{0}'.format(filter_number)] = filter_string
        return search_parameters

    def execute(self, session, count=9, headers=None):
        search_parameters = self.build_search_parameters(session, count)
        log.info(simplejson.dumps({'search_parameters': search_parameters}))
        return session.get('https://www.okcupid.com/match',
                           params=search_parameters,
                           headers=headers).json()['html']


class MatchCardExtractor(object):

    def __init__(self, div):
        self._div = div

    @property
    def username(self):
        return self._div.xpath(".//div[@class = 'username']/a")[0].text_content()

    @property
    def age(self):
        return int(self._div.xpath(".//span[@class = 'age']/text()")[0])

    @property
    def location(self):
        return helpers.replace_chars(self._div.xpath(".//span[@class = 'location']/text()")[0])

    @property
    def id(self):
        try:
            raw_id = self._div.xpath(".//li[@class = 'current-rating']/@id")[0]
            return re.search(r'\d{2,}', raw_id).group()
        except IndexError:
            return self._div.xpath(".//button[@id = 'personality-rating']/@data-tuid")[0]

    @property
    def match_percentage(self):
        return int(self._div.xpath(
            ".//div[@class = 'percentage_wrapper match']")[0].xpath(
                ".//span[@class = 'percentage']")[0].text.strip('%'))

    @property
    def enemy_percentage(self):
        return int(self._div.xpath(
            ".//div[@class = 'percentage_wrapper enemy']")[0].xpath(
                ".//span[@class = 'percentage']")[0].text.strip('%'))

    @property
    def rating(self):
        try:
            rating_div = self._div.xpath(".//li[@class = 'current-rating']")
            rating_style = rating_div[0].attrib['style']
            width_percent = int(''.join(c for c in rating_style if c.isdigit()))
            return int((width_percent / 100) * 5)
        except IndexError:
            return 0

    @property
    def contacted(self):
        return bool(self._div.xpath(".//span[@class = 'fancydate']"))

    @property
    def as_dict(self):
        return {
            'name': self.username,
            'age': self.age,
            'location': self.location,
            'match': self.match_percentage,
            'enemy': self.enemy_percentage,
            'id': self.id,
            'rating': self.rating,
            'contacted': self.contacted
        }


def search(session=None, count=9, **kwargs):
    session = session or objects.Session.login()
    profiles_response = SearchExecutor(**kwargs).execute(session, count)
    log.info(simplejson.dumps({'profiles_response': profiles_response}))
    if not profiles_response.strip(): return []
    profiles_tree = html.fromstring(profiles_response)
    match_card_elems = profiles_tree.xpath(".//div[@class='match_card opensans']")
    profiles = []
    for div in match_card_elems:
        match_card_extractor = MatchCardExtractor(div)
        profiles.append(objects.Profile(session, match_card_extractor.username,
                                        match_card_extractor.age,
                                        match_card_extractor.location,
                                        match_card_extractor.match_percentage,
                                        enemy=match_card_extractor.enemy_percentage,
                                        id=match_card_extractor.id,
                                        rating=match_card_extractor.rating,
                                        contacted=match_card_extractor.contacted))
    return profiles
