import datetime
import json

from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from .forms import ConfirmationForm, MatchForm, SingleGameForm
from .models import Game


@login_required
@require_POST
def match_submit(request):
    form = MatchForm(request.POST, submitter=request.user)

    if form.is_valid():
        won, lost = form.save()
        messages.success(
            request,
            ("<strong>Updated!</strong> {} wins and {} losses have "
             "been submitted for approval!").format(won, lost)
        )
        return redirect('/')
    return render(request, 'games/match.error.html', {'match_form': form})


@login_required
@require_POST
def single_game_submit(request):
    form = SingleGameForm(request.POST, submitter=request.user)

    if form.is_valid():
        form.save()
        messages.success(
            request,
            "<strong>Updated!</strong> Your game has been submitted "
            "for approval!"
        )
        return redirect('/')
    return render(request, 'games/single-game.error.html', {'game_form': form})


@login_required
@require_POST
def submit_confirmation(request):
    """ Processes a game confirmation request. """
    form = ConfirmationForm(request.POST)

    if form.is_valid():
        accepted, confirmed = form.save(request.user)
    else:
        accepted, confirmed = False, False

    if not accepted:
        alert_type = messages.error
        message_text = ("Oh no!", "We couldn't record your update. Try again?")

    elif confirmed:
        alert_type = messages.success
        message_text = ("Tyte!", "We've confirmed your game, "
                        "the rankings have been updated.")

    else:
        alert_type = messages.warning
        message_text = ("Okay!", "We've deleted the game, "
                        "and notified your opponent!")

    alert_type(request, "<strong>{0}</strong> {1}".format(*message_text))

    if request.is_ajax():
        return render(request, 'include/messages.html')

    return redirect('games:game_confirm')


@login_required
def game_confirm(request):
    """ Show the user a table of unconfirmed games, and allow them to confirm
    or reject them.
    """
    games = Game.objects.unconfirmed_games(request.user)
    return render(request, 'games/confirm.html', {
        'games': games,
    })


@login_required
def awaiting_confirmation(request):
    games = Game.objects.awaiting_confirmation(request.user)
    return render(request, 'games/awaiting-confirmation.html', {
        'games': games,
    })


def get_player_record(player, rankings):
    delta = datetime.datetime.now() - datetime.timedelta(days=14)

    games = Game.objects.confirmed().played_by(player)
    games = games.filter(date_created__gte=delta)
    games = games.order_by('date_created')
    games = games.values_list('winner__id', 'loser__id')

    record = {}
    for game in games:
        if game[0] == player.id:
            record.setdefault(game[1], []).append(1)
        else:
            record.setdefault(game[0], []).append(-1)

    for rank in (r for r in rankings if r.id in record):
        rank.record = json.dumps(record[rank.id][:30], separators=(',', ':'))

    return rankings


def index(request):
    user = request.user
    is_authenticated = user.is_authenticated()

    if is_authenticated:
        single_game_form = SingleGameForm(submitter=user)
        match_form = MatchForm(submitter=user)

    else:
        single_game_form = match_form = None

    query = """
        SELECT
            COUNT(*)
        FROM
            games_game
        WHERE
            games_game.%s_id = auth_user.id
        AND
            games_game.confirmed = TRUE
    """

    rankings = User.objects.select_related().filter(is_active=True).extra(
        select={
            'total_wins': query % 'winner',
            'total_losses': query % 'loser',
        },
    ).order_by('-rating__exposure', 'first_name')

    if is_authenticated:
        rankings = get_player_record(user, rankings)

    return render(request, 'games/index.html', {
        'is_authenticated': is_authenticated,
        'match_form': match_form,
        'rankings': rankings,
        'single_game_form': single_game_form,
    })
