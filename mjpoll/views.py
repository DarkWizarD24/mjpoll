# coding: utf-8
"""Manage the differents pages of the site"""

import markdown
import bleach
from urlparse import urlparse
from datetime import datetime

from flask import Flask, render_template, request, flash, redirect, url_for
from flask_babel import gettext, format_datetime

from mjpoll import app, babel
from data import get_poll, get_results, get_voter_ballot, add_update_ballot, get_own_polls, get_participate_polls, delete_poll, insert_poll, get_ballot_voters

USER = 'Bob' #TODO


def sort_choices_with_rank(choice_with_rank):
    return choice_with_rank[1]


@babel.localeselector
def get_locale():
    return request.accept_languages.best_match(app.config['LANGUAGES'].keys())


def set_target(attrs, new=False):
    p = urlparse(attrs['href'])
    attrs['target'] = '_blank'
    return attrs


@app.template_filter('md_message')
def md_message_filter(s):
    """Filter that convert to markdown and allow only tag legal for messages"""
    return bleach.linkify(bleach.clean(markdown.markdown(s), tags=['strong', 'em', 'a', 'ul', 'li', 'p', 'br'], strip=True), callbacks=[set_target])


@app.template_filter('md_choice')
def md_choice_filter(s):
    """Filter that convert to markdown and allow only tag legal for choices"""
    return bleach.linkify(bleach.clean(markdown.markdown(s), tags=['strong', 'em', 'a'], strip=True), callbacks=[set_target])


@app.route('/')
def new_poll():
    return render_template('poll.html')


@app.route('/list')
def list_poll():
    own_polls = get_own_polls(USER)
    if own_polls is None:
        own_polls = []

    participate_polls = get_participate_polls(USER)
    if participate_polls is None:
        participate_polls = []

    return render_template('list.html', own_polls=own_polls, participate_polls=participate_polls)


@app.route('/delete/<poll>')
def delete(poll):
    delete_poll(poll)
    flash(gettext(u'Poll deleted'), 'success')
    return redirect(url_for('list_poll'))


@app.route('/cast', methods=['POST'])
def cast():
    if request.method == 'POST':
        if 'poll' not in request.form:
            return render_template('error.html', message=gettext(u'Error: cast invalid data'))

        choices = {}
        for param, value in request.form.items():
            if param.startswith('choice_'):
                choices[int(param.split('_')[1])] = int(value)

        result = add_update_ballot(voter=USER, poll=request.form['poll'], choices=choices)
        if result:
            flash(gettext(u'Ballot saved'), 'success')
        else:
            flash(gettext(u'Invalid ballot'), 'danger')
        return redirect(url_for('ballot_or_results', poll=request.form['poll']))
    else:
        return render_template('error.html', message=gettext(u'Error: cast without data'))


@app.route('/preview', methods=['POST'])
def preview():
    if request.method == 'POST':
        if 'title' in request.form:
            title = request.form['title']
        else:
            title = ""
            
        if 'message' in request.form:
            message = request.form['message']
        else:
            message = ""
            
        if 'end_date' in request.form:
            try:
                end_date = format_datetime(datetime.strptime(request.form['end_date'], '%Y-%m-%dT%H:%M'))
            except:
                end_date = format_datetime(datetime.now())
        else:
            end_date = format_datetime(datetime.now())
            
        choices = []
        for param, value in request.form.items():
            if param.startswith('choice_'):
                choices.append(value)

        return render_template('preview.html', title=title, message=message, end_date=end_date, choices=choices)
    else:
        return render_template('error.html', message=gettext(u'Error: preview without data'))


@app.route('/save', methods=['POST'])
def save():
    if request.method == 'POST':
        for param, value in request.form.items():
            print param, value
            
        if 'poll_title' not in request.form:
            return render_template('error.html', message=gettext(u'Error: poll without title'))
            
        if 'poll_message' not in request.form:
            return render_template('error.html', message=gettext(u'Error: poll without message'))
            
        if 'poll_end_date' not in request.form:
            return render_template('error.html', message=gettext(u'Error: poll without date'))
        else:
            try:
                end_date = datetime.strptime(request.form['poll_end_date'], '%Y-%m-%dT%H:%M')
            except:
                return render_template('error.html', message=gettext(u'Error: poll with invalid date'))
            
        choices = []
        for param, value in request.form.items():
            if param.startswith('poll_choice_'):
                if value == "":
                    return render_template('error.html', message=gettext(u'Error: poll with an empty choice'))
                choices.append(value)

        if not choices:
            return render_template('error.html', message=gettext(u'Error: poll with no choices'))
        
        uid = insert_poll(title=request.form['poll_title'], message=request.form['poll_message'], choices=choices, end_date=end_date, owner=USER)
        if uid is None:
            flash(gettext(u'Error: saving poll failed'), 'danger')
        else:
            flash(gettext(u'Message: poll created with url %(url)s', url=url_for('ballot_or_results', poll=uid, _external=True)), 'success')
        return redirect(url_for('list_poll'))
    else:
        return render_template('error.html', message=gettext(u'Error: poll without data'))


@app.route('/<poll>')
def ballot_or_results(poll):
    """IF the poll is open, display the ballot page. Otherwise display the results page"""

    poll = get_poll(poll)

    if poll is None:
        return render_template('error.html', message=gettext(u'Error: poll do not exits'))
    else:
        poll['end_date'] = format_datetime(poll['end_date'])
        if poll['closed']:
            results = get_results(poll)

            if results is None:
                return render_template('error.html', message=gettext(u'Error: poll with not results'))

            choices_by_rank = []
            choices_with_rank = []
            for choice, result in results.items():
                choices_with_rank.append([choice, result['rank'][0] if isinstance(result['rank'], list) else result['rank']])
            choices_with_rank.sort(key=sort_choices_with_rank)
            choices_by_rank = [choice_with_rank[0] for choice_with_rank in choices_with_rank]

            return render_template('results.html', poll=poll, results=results, choices_by_rank=choices_by_rank)
        else:
            ballot = get_voter_ballot(USER, poll['uid'])
            voters = get_ballot_voters(poll['uid'])

            if ballot is None:
                ballot = {}
                for choice in poll['choices']:
                    ballot[choice['id']] = 0
            
            if voters is None:
                voters = []

            return render_template('ballot.html', poll=poll, ballot=ballot, voters=voters)
