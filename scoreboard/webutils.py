"""Utility functions for website generation."""

import datetime

import dateutil.parser
import jinja2

from . import model
from . import modelutils
from . import constants as const

PRETTY_TIME_FORMAT = '%-d %B %Y'
TIME_FORMAT = '<time class="timeago" datetime="{ts}Z">{t}</time>'


def prettyint(value):
    """Jinja filter to prettify ints.

    eg, 1234567 to '1,234,567'.
    """
    return "{0:,}".format(value)


def prettydur(duration, hours=False):
    """Jinja filter to convert seconds to a pretty duration "HH:MM:SS".

    Parameters:
        hours (bool) Convert to only hours (with a minimum of 1 -- for player
            'hours played' metric).

    Examples:
        prettydur(170) => '0:2:50'
        prettydur(0, hours=True) => '1'
        prettydur(86400, hours=True) => '24'
    """
    if type(duration) != int:
        duration = int(duration)
    delta = datetime.timedelta(seconds=duration)
    if hours:
        dur = delta.total_seconds() / 3600
        return str(int(dur)) if dur > 1 else '1'
    else:
        return str(delta)


def prettycounter(counter):
    """Jinja filter to convert a counter dict to pretty text.

    Sorts by lexical order of keys.

    eg, {'c':1, 'b': 3, 'a': 2} to 'a (2), c (1), b (3)'.
    """
    return ", ".join(
        "{open}{k}&nbsp;({v}){close}".format(
            k=k,
            v=v,
            open="" if v > 0 else '<span class="text-muted">',
            close="" if v > 0 else '</span>')
        for k, v in sorted(counter.items(), key=lambda i: i[0]))


def prettycrawldate(d):
    """Jinja filter to convert crawl date string to pretty text."""
    d = modelutils.crawl_date_to_datetime(d)
    return prettydate(d)


def prettydate(d):
    """Jinja filter to convert datetime object to pretty text."""
    return TIME_FORMAT.format(ts=d.isoformat(),
                              t=d.strftime(PRETTY_TIME_FORMAT))


def link_player(player, urlbase):
    """Convert a player name into a link."""
    return "<a href='{base}/players/{name}.html'>{name}</a>".format(
        base=urlbase, name=player)


@jinja2.environmentfilter
def gamestotable(env,
                 games,
                 *,
                 prefix_col=None,
                 prefix_col_title=None,
                 show_player=False,
                 winning_games=False,
                 sort_col=None,
                 limit=None,
                 skip_header=False):
    """Jinja filter to convert a list of games into a standard table.

    Parameters:
        env: Environment -- passed in automatically
        prefix_col (str): Add an extra column at the start with data from
                          game.raw_data.
                          The table will also be sorted by this column.
        prefix_col_title (str): Title for the prefix_col column
        sort_col (str): Sort the table by this column from game.raw_data.
        show_player (bool): Show the player name column
        winning_games (bool): The table has only winning games, so don't show
                              place or end columns, and do show runes.
        limit (int): The table won't display more games than this.
        skip_header (bool): Skip the header?

    Returns: (string) '<table>contents</table>'.
    """

    def format_trow(game):
        """Convert a game to a table row."""
        return trow.format(
            win='table-success' if game.ktyp == 'winning' else '',
            prefix_col='' if not prefix_col else "<td>%s</td>" %
            game.raw_data.get(prefix_col),
            player_row='' if not show_player else "<td>%s</td>" % link_player(
                game.name, env.globals['urlbase']),
            score=prettyint(game.sc),
            character=game.char,
            god=game.god,
            place="" if winning_games else "<td>%s</td>" % game.place,
            end="" if winning_games else "<td>%s</td>" % game.raw_data.get(
                'tmsg'),
            turns=prettyint(game.turn),
            duration=prettydur(game.dur),
            date=prettydate(game.end),
            version=game.v,
            morgue=morgue_link(game))

    t = """<table class="{classes}">
          <thead>
            <tr>
            {thead}
            </tr>
          </thead>
          <tbody>
            {tbody}
          </tbody>
        </table>"""

    thead = """{prefix}
              {player}
              <th class="text-xs-right">Score</th>
              <th>Combo</th>
              <th>God</th>
              {place}
              {end}
              <th class="text-xs-right">Turns</th>
              <th class="text-xs-right">Duration</th>
              <th class="text-xs-right">Date</th>
              <th>Version</th>
              <th>Morgue</th>""".format(
        prefix='' if not prefix_col else '<th>%s</th>' % prefix_col_title,
        player='' if not show_player else '<th>Player</th>',
        place='' if winning_games else '<th>Place</th>',
        end='' if winning_games else '<th>End</th>')

    trow = """<tr>
      {prefix_col}
      {player_row}
      <td class="text-xs-right">{score}</td>
      <td>{character}</td>
      <td>{god}</td>
      {place}
      {end}
      <td class="text-xs-right">{turns}</td>
      <td class="text-xs-right">{duration}</td>
      <td class="text-xs-right">{date}</td>
      <td>{version}</td>
      <td>{morgue}</td>
    </tr>"""

    if limit:
        games = games[:limit]

    if sort_col:
        games = sorted(games, key=lambda g: g['raw_data'][sort_col])
    elif prefix_col:
        games = sorted(games, key=lambda g: g['raw_data'][prefix_col])

    return t.format(classes=const.TABLE_CLASSES,
                    thead=thead if not skip_header else '',
                    tbody="\n".join(format_trow(game) for game in games))


def streakstotable(streaks, show_player=True, show_loss=True, limit=None):
    """Jinja filter to convert a list of streaks into a standard table.

    Parameters:
        show_player (bool): Show the player name column.
        show_loss (bool): Show the losing game column.
        limit (int): The table won't display more games than this.

    Returns: (string) '<table>contents</table>'.
    """

    def format_trow(streak, show_player, show_loss):
        """Convert a streak to a table row."""
        player = ""
        loss = ""
        if show_player:
            player = "<td><a href='players/{player}.html'>{player}<a></td>".format(
                player=model.game(streak['wins'][-1]).name)
        if show_loss:
            loss = "<td>%s</td>" % (morgue_link(
                model.game(streak['streak_breaker']),
                model.game(streak['streak_breaker']).char) if
                                    'streak_breaker' in streak else '')

        return trow.format(
            wins=len(streak['wins']),
            player=player,
            games=', '.join(morgue_link(
                model.game(g), model.game(g).char) for g in streak['wins']),
            start=prettydate(dateutil.parser.parse(streak['start'])),
            end=prettydate(dateutil.parser.parse(streak['end'])),
            streak_breaker=loss)

    t = """<table class="{classes}">
          <thead>
            <tr>
            {thead}
            </tr>
          </thead>
          <tbody>
            {tbody}
          </tbody>
        </table>"""

    thead = """<th class="text-xs-right">Wins</th>
               {player}
               <th>Games</th>
               <th class="date-table-col text-xs-right">First Win</th>
               <th class="date-table-col text-xs-right">Last Win</th>
               {loss}""".format(
        player='' if not show_player else '<th>Player</th>',
        loss='' if not show_loss else '<th>Loss</th>')

    trow = """<tr>
        <td class="text-xs-right">{wins}</td>
        {player}
        <td>{games}</td>
        <td class="text-xs-right">{start}</td>
        <td class="text-xs-right">{end}</td>
        {streak_breaker}
        </tr>"""

    if limit:
        streaks = streaks[:limit]

    return t.format(classes=const.TABLE_CLASSES,
                    thead=thead,
                    tbody="\n".join(format_trow(streak, show_player, show_loss)
                                    for streak in streaks))


def mosthighscorestotable(highscores):
    """Jinja filter to convert a list of combo highscores by players into a standard table."""
    table = """<table class="{classes}">
          <thead>
            <tr>
              <th>Player</th>
              <th class="text-xs-right">Highscores</th>
              <th>Combos</th>
            </tr>
          </thead>
          <tbody>
            {tbody}
          </tbody>
        </table>"""

    tbody = ""
    for entry in highscores:
        combos = ', '.join([morgue_link(game, game.char) for game in entry[1]])
        tbody += ("""<tr>
                       <td>%s</td>
                       <td class="text-xs-right">%s</td>
                       <td>%s</td>
                     </tr>""" %
                  ("<a href='players/{player}.html'>{player}<a>".format(
                      player=entry[0]), len(entry[1]), combos))

    return table.format(classes=const.TABLE_CLASSES, tbody=tbody)


def recordsformatted(records):
    result = """{race}
                {role}
                {god}
                {combo}"""

    race = ''
    role = ''
    god = ''
    combo = ''

    if records['race']:
        race = "<p><strong>Species (%s):</strong> %s</p>" % (
            len(records['race']), ', '.join([morgue_link(game, game.rc)
                                             for game in records['race']]))

    if records['role']:
        role = "<p><strong>Backgrounds (%s):</strong> %s</p>" % (
            len(records['role']), ', '.join([morgue_link(game, game.bg)
                                             for game in records['role']]))

    if records['god']:
        god = "<p><strong>Gods (%s):</strong> %s</p>" % (
            len(records['god']), ', '.join([morgue_link(game, game.god)
                                            for game in records['god']]))

    if records['combo']:
        combo = "<p><strong>Combos (%s):</strong> %s</p>" % (
            len(records['combo']), ', '.join([morgue_link(game, game.char)
                                              for game in records['combo']]))

    return result.format(race=race, role=role, god=god, combo=combo)


def morgue_link(game, text="Morgue"):
    """Returns a hyperlink to a morgue file.

    Game can be either a gid string or a game object.
    """
    if type(game) is str:
        # Treat as gid
        game = model.game(game)
    elif 'raw_data' not in game:
        # Treat as raw_data
        game = model.game(game['gid'])
    if not game:
        return "Not Found"
    result = "<a href='" + modelutils.morgue_url(game) + "'>" + text + "</a>"
    return result
