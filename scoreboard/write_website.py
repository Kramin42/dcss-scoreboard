"""Take generated score data and write out all website files."""

import os
import json
import time
import subprocess
import datetime

import jsmin
import jinja2

from . import model
from . import webutils
import scoreboard.constants as const
from . import orm

WEBSITE_DIR = 'website'

def jinja_env(urlbase):
    """Create the Jinja template environment."""
    template_path = os.path.join(os.path.dirname(__file__), 'html_templates')
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(template_path))
    env.filters['prettyint'] = webutils.prettyint
    env.filters['prettydur'] = webutils.prettydur
    env.filters['prettycounter'] = webutils.prettycounter
    env.filters['prettycrawldate'] = webutils.prettycrawldate
    env.filters['gamestotable'] = webutils.gamestotable
    env.filters['streakstotable'] = webutils.streakstotable
    env.filters['prettydate'] = webutils.prettydate
    env.filters['link_player'] = webutils.link_player
    env.filters['morgue_link'] = webutils.morgue_link
    env.filters['mosthighscorestotable'] = webutils.mosthighscorestotable
    env.filters['recordsformatted'] = webutils.recordsformatted

    env.globals['tableclasses'] = const.TABLE_CLASSES

    if urlbase:
        env.globals['urlbase'] = urlbase
    else:
        env.globals['urlbase'] = os.path.join(os.getcwd(), WEBSITE_DIR)

    return env


def achievement_data(ordered=False):
    """Load achievement data.

    If ordered is True, the achievements are returned as a list in display
    order, otherwise they are returned as a dict keyed off the achievement ID.
    """
    path = os.path.join(os.path.dirname(__file__), 'achievements.json')
    return json.load(open(path))


def player_records(player, race_highscores, role_highscores, combo_highscores,
                   god_highscores):
    """Return a dictionary of player records.

    Dict is of the form { 'race': [('Ce', gid), ('Vp', gid)], 'role': [],
        'combo': [...], 'god': [...] }.
    """
    records = {'race': [], 'role': [], 'combo': [], 'god': []}
    for game in race_highscores:
        if game.name == player:
            records['race'].append(game)
    for game in role_highscores:
        if game.name == player:
            records['role'].append(game)
    for game in combo_highscores:
        if game.name == player:
            records['combo'].append(game)
    for game in god_highscores:
        if game.name == player:
            records['god'].append(game)

    return records


def setup_website_dir(env, path, all_players):
    print("Writing HTML to %s" % path)
    if not os.path.exists(path):
        print("mkdir %s/" % path)
        os.mkdir(path)

    print("Copying static assets")
    src = os.path.join(os.path.dirname(__file__), 'html_static')
    dst = os.path.join(path, 'static')
    subprocess.run(['rsync', '-a', src + '/', dst + '/'])

    print("Generating player list")
    with open(os.path.join(dst, 'js', 'players.json'), 'w') as f:
        f.write(json.dumps([p.name for p in all_players]))


    print("Writing minified local JS")
    scoreboard_path = os.path.join(WEBSITE_DIR, 'static/js/dcss-scoreboard.js')
    with open(scoreboard_path, 'w') as f:
        template = env.get_template('dcss-scoreboard.js')
        f.write(jsmin.jsmin(template.render()))


def write_player_stats(*, player, stats, outfile, achievements, streaks,
                       active_streak, template, records):
    """Write stats page for an individual player.

    Parameters:
        player (str) Player Name
        stats (dict) Player's stats dict from model.player_stats
        outfile (str) Output filename
        achievements (dict) Player's achievements
        streaks (list) Player's streaks or []
        active_streak (dict) Player's active streak or {}
        template (Jinja template) Template to render with.
        records (dict) Player's global highscores

    Returns: None.
    """
    recent_games = model.recent_games(player=player)
    all_wins = model.recent_games(wins=True, player=player, num=None)
    race_wins = model.games_by_type(player, 'rc', const.PLAYABLE_RACES)
    background_wins = model.games_by_type(player, 'bg', const.PLAYABLE_ROLES)
    god_wins = model.games_by_type(player, 'god', const.PLAYABLE_GODS)
    last_active = model.last_active(player)

    with open(outfile, 'w', encoding='utf8') as f:
        f.write(template.render(player=player,
                                stats=stats,
                                last_active=last_active,
                                all_wins=all_wins,
                                race_wins=race_wins,
                                background_wins=background_wins,
                                god_wins=god_wins,
                                achievement_data=achievements,
                                const=const,
                                records=records,
                                streaks=streaks,
                                active_streak=active_streak,
                                recent_games=recent_games))


def write_index(s, env):
    print("Writing index")
    with open(
            os.path.join(WEBSITE_DIR, 'index.html'),
            'w', encoding='utf8') as f:
        template = env.get_template('index.html')
        f.write(template.render(recent_wins=model.list_games(s, winning=True,
                                                             limit=const.GLOBAL_TABLE_LENGTH),
                                active_streaks=[],
                                overall_highscores=model.highscores(s),
                                combo_high_scores=model.combo_highscore_holders(s)))


def write_website(players=set(), urlbase=None):
    """Write all website files.

    Paramers:
        urlbase (str) Base URL for the website
        players (iterable of strings) Only write these player pages.
            If you pass in False, no player pages will be rebuilt.
            If you pass in None, all player pages will be rebuilt.
    """
    start = time.time()

    env = jinja_env(urlbase)

    s = orm.get_session()

    all_players = sorted(model.list_players(s), key=lambda p: p.name)
    if players is None:
        players = all_players
    elif not players:
        players = []


    setup_website_dir(env, WEBSITE_DIR, all_players)

    write_index(s, env)

    print("Writing streaks")
    with open(
            os.path.join(WEBSITE_DIR, 'streaks.html'),
            'w',
            encoding='utf8') as f:
        template = env.get_template('streaks.html')
        f.write(template.render(streaks=sorted_streaks,
                                active_streaks=sorted_active_streaks))

    print("Writing highscores")
    with open(
            os.path.join(WEBSITE_DIR, 'highscores.html'),
            'w',
            encoding='utf8') as f:
        template = env.get_template('highscores.html')
        f.write(template.render(overall_highscores=overall_highscores,
                                race_highscores=race_highscores,
                                role_highscores=role_highscores,
                                god_highscores=god_highscores,
                                combo_highscores=combo_highscores,
                                fastest_wins=fastest_wins,
                                shortest_wins=shortest_wins))

    print("Writing %s player pages... " % len(players))
    start2 = time.time()
    player_html_path = os.path.join(WEBSITE_DIR, 'players')
    if not os.path.exists(player_html_path):
        os.mkdir(player_html_path)
    achievements = achievement_data()
    template = env.get_template('player.html')

    n = 0
    for player in players:
        stats = model.get_player_stats(player)
        streaks = player_streaks.get(player.lower(), [])
        active_streak = active_streaks.get(player.lower(), {})
        records = player_records(player, race_highscores, role_highscores,
                                 combo_highscores, god_highscores)
        # Don't make pages for players with no stats
        # This can happen for players that are blacklisted, eg bots
        # and griefers.
        if stats is None:
            continue
        # Don't make pages for players with no games played
        if stats['games'] == 0:
            continue

        outfile = os.path.join(player_html_path, player + '.html')
        write_player_stats(player=player,
                           stats=stats,
                           outfile=outfile,
                           achievements=achievements,
                           streaks=streaks,
                           active_streak=active_streak,
                           template=template,
                           records=records)
        n += 1
        if not n % 10000:
            print(n)
    end = time.time()
    print("Wrote player pages in %s seconds" % round(end - start2, 2))
    print("Wrote website in %s seconds" % round(end - start, 2))


if __name__ == "__main__":
    write_website()
