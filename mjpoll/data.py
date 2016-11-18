# coding: utf-8
"""Provide acces to the data"""

import sqlite3
import os
import copy
import math
from uuid import uuid4
from datetime import datetime
from collections import defaultdict

from flask import g

from mjpoll import app

app.config['DATABASE'] = os.path.realpath(os.path.join(app.root_path, '../data/mjpoll.db'))


def get_db():
    """Give access to the database"""

    db = getattr(g, '_database', None)
    if db is None:
        if not os.path.exists(os.path.dirname(app.config['DATABASE'])):
            os.mkdir(os.path.dirname(app.config['DATABASE']))

        db = g._database = sqlite3.connect(app.config['DATABASE'], detect_types=sqlite3.PARSE_DECLTYPES)
        db.row_factory = sqlite3.Row
        # Enable foreign key verifications
        db.execute('pragma foreign_keys=ON')
    return db


@app.teardown_appcontext
def close_connection(exception):
    """When the application exit, close the database"""
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()


def init_db():
    """
    Can be called in python interpreter to create the database:
    >>> from mjpoll.db import init
    >>> init()
    """

    with app.app_context():
        db = get_db()
        with app.open_resource('schema.sql', mode='r') as f:
            db.cursor().executescript(f.read())
        db.commit()


def query_read(query, args=(), one=False):
    """Execute a read query on the database and retrieve the data"""
    cur = get_db().execute(query, args)
    rv = cur.fetchall()
    cur.close()
    return (rv[0] if rv else None) if one else rv


def get_entry(table, field, value):
    """Get the first entry of the table with its field equals to value"""

    return query_read('SELECT * FROM ' + table + ' WHERE ' + field + ' = ?', [value], one=True)


def get_entries(table, field, value):
    """Get all entries of the table with their field equals to value"""

    return query_read('SELECT * FROM ' + table + ' WHERE ' + field + ' = ?', [value])


def insert_poll(title, message, choices, end_date, owner):
    """
    Create a poll.

    :return: uid or None if the insertion failed
    """

    uid = str(uuid4())

    db = get_db()

    with db:
        get_db().execute("INSERT INTO polls (uid, title, message, end_date, owner) VALUES (?, ?, ?, ?, ?)", [uid, title, message, end_date, owner])

        choice_db = []
        for choice in choices:
            choice_db.append((uid, choice))

        get_db().executemany("INSERT INTO choices (poll, text) VALUES (?, ?)", choice_db)

        return uid

    return None


def add_update_ballot(voter, poll, choices):
    """
    Add a ballot from an user or update if if exists

    :param user: Name of the voter
    :param poll: UID of the poll
    :param choices: Choices associated with their grade
    :type choices: {choice_id: grade,}
    :return: True if the operation is a success
    """

    db = get_db()

    with db:
        poll = get_poll(poll)
        if poll is None or poll['closed'] is True or len(poll['choices']) != len(choices):
            return False

        ballot = []
        for choice, grade in choices.iteritems():
            ballot.append((voter, poll['uid'], choice, grade))

        get_db().executemany("INSERT OR REPLACE INTO ballots (voter, poll, choice, grade) VALUES (?, ?, ?, ?)", ballot)

    return True


def get_poll(poll):
    """Get a poll from the database"""
    poll = get_entry('polls', 'uid', poll)

    if poll is None:
        return None

    poll = dict(poll)

    poll['choices'] = []
    for choice in get_entries('choices', 'poll', poll['uid']):
        poll['choices'].append(dict(choice))
    poll['choices'].sort(key=lambda x: x['id'])

    poll['closed'] = poll['end_date'] < datetime.now()
    return poll


def get_own_polls(owner):
    """Get all polls owned by an user from the database"""
    polls_db = get_entries('polls', 'owner', owner)

    if polls_db is None:
        return None

    polls = []
    for poll in polls_db:
        poll = dict(poll)
        poll['closed'] = poll['end_date'] < datetime.now()
        polls.append(poll)

    return polls


def get_participate_polls(voter):
    """Get all polls the user has vote for from the database"""
    ballots = get_entries('ballots', 'voter', voter)

    if ballots is None:
        return None

    polls_uid = set()
    for ballot in ballots:
        polls_uid.add(ballot['poll'])
        
    polls = []
    for poll_uid in polls_uid:
        poll = get_poll(poll_uid)
        if poll is not None:
            polls.append(poll)

    if not polls:
        return None

    return list(polls)


def delete_poll(poll):
    """Delete a poll from the database"""
    get_db().execute('DELETE FROM ballots WHERE poll = ?;', [poll])
    get_db().execute('DELETE FROM results WHERE poll = ?;', [poll])
    get_db().execute('DELETE FROM choices WHERE poll = ?;', [poll])
    get_db().execute('DELETE FROM polls WHERE uid = ?;', [poll])
    get_db().commit()


def get_voter_ballot(voter, poll):
    """Get ballot from a user from the database

    :param voter: name of the voter
    :param poll: UID of the poll
    :return: [(choices.id, ballots.grade),]
    """
    ballot = query_read("SELECT choices.id, ballots.grade FROM choices JOIN ballots ON ballots.poll = ? and choices.id = ballots.choice and ballots.voter = ? ORDER BY choices.id;", [poll, voter])

    if not ballot:
        return None

    return dict(ballot)

def get_ballot_voters(poll):
    """
    Return the list of all the voters from a poll
    :param poll: UID of the poll
    :return: [str(voter),]
    """
    voters = query_read("SELECT voter FROM ballots WHERE poll = ? ORDER BY voter;", [poll])

    if not voters:
        return None

    return [voter[0] for voter in voters]

def choice_compute(choice):
    if len(choice['votes']) % 2 == 0:
        middle_point = len(choice['votes']) / 2
    else:
        middle_point = (len(choice['votes']) + 1) / 2
    choice['median'] = choice['votes'][middle_point]
    choice['better'] = len([grade for grade in choice['votes'] if grade > choice['median']])
    choice['worse'] = len([grade for grade in choice['votes'] if grade < choice['median']])


def choice_wheight_fct(ballots_count):
    """
    :return: A function to attribute weight to choice with a range adapted to the number of ballots.
    """
    magnitude_order = math.pow(10, int(math.log10(ballots_count) + 1))

    def choice_weight(choice):
        """
        :return: A weight to a choice that allow to rank it.
        """
        return choice[1]['median'] * 10 * magnitude_order + ((5 * magnitude_order + choice[1]['better']) if choice[1]['better'] > choice[1]['worse'] else (magnitude_order - choice[1]['worse']))

    return choice_weight


def decimate_middle_point(votes):
    """Remove the middle point value of a list"""
    if len(votes) % 2 == 0:
        middle_point = len(votes) / 2
    else:
        middle_point = (len(votes) + 1) / 2

    del votes[middle_point]


def list_equals_values(lst):
    return not lst or lst.count(lst[0]) == len(lst)


def rank_choices(choices, ballots_count):
    """
    :return: For each choice, its ranks (tie choices have a list of ranks)
    """

    choice_weight = choice_wheight_fct(ballots_count)
    ranks = {}

    # Transform the choices dictionnary to a list to be able to sort it
    choices = copy.copy(choices.items())

    # At first all the results are stated as ties
    ties = [[choices, list(range(1, len(choices) + 1))]]

    # Until all tie are breaks
    while len(ties) > 0:
        # Pop the last tie of the list and try to break the ties
        group = ties.pop()
        choices = group[0]

        # If all choices in a tie group have the same votes, give them the same ranks
        if list_equals_values([choice[1]['votes'] for choice in choices]):
            for choice in group[0]:
                ranks[choice[0]] = group[1]
            continue

        # Sort the element of the tie group
        choices.sort(key=choice_weight, reverse=True)

        group_ranks = {}
        for i in range(len(choices)):
            group_ranks[choices[i][0]] = i + group[1][0]

        # Detect remaining ties and store them by groups
        group_ties = [] # Associate the choice to their possibles ranks
        for i in range(len(choices) -1):
            if choice_weight(choices[i]) == choice_weight(choices[i + 1]):
                found = False
                for tie in group_ties:
                    if choices[i] in tie[0]:
                        tie[0].append(choices[i + 1])
                        tie[1].append(group_ranks[choices[i + 1][0]])
                        found = True
                if not found:
                    group_ties.append([[choices[i], choices[i + 1]], [group_ranks[choices[i][0]], group_ranks[choices[i + 1][0]]]])


        # Store the ranks
        for i in range(len(choices)):
            ranks[choices[i][0]] = i + group[1][0]

        # Add new ties group to the list of ties
        ties.extend(group_ties)

        # Decimate values from ties chocies
        for group in group_ties:
            for choice in group[0]:
                decimate_middle_point(choice[1]['votes'])
                choice_compute(choice[1])

    return ranks


def get_results(poll):
    """
    Get cached results from the poll or compute them.

    After computation, ballots are destroyed.

    :param poll: Poll from get_poll function
    """

    assert poll is not None, "Invalid poll: None"

    if not poll['closed']:
        return None

    results = {}

    # Get cached results
    results_db = get_entries('results', 'poll', poll['uid'])

    # If no cache, compute the results and store them
    if len(results_db) == 0:
        ballots = get_entries('ballots', 'poll', poll['uid'])

        # If no ballots provide, no results
        if len(ballots) == 0:
            return None

        # Number of ballots cast
        ballots_count = len(ballots) / len(poll['choices'])

        # Build data structures
        choices = {}
        results = {}
        for choice in poll['choices']:
            choices[choice['id']] = {'votes': [0] * 7}
            results[choice['id']] = {'ballots': ballots_count}

        # Count the number of vote for each grade for each choice
        for ballot in ballots:
            choices[ballot['choice']]['votes'][ballot['grade']] += 1

        # Store the count in percentage for display purposes
        for choice in choices:
            results[choice]['percentages'] = []
            for vote in choices[choice]['votes']:
                results[choice]['percentages'].append(100 * vote / ballots_count)

        # Transfrom the number of vote to a list of votes
        for _, choice in choices.items():
            votes = []
            for i in range(len(choice['votes'])):
                votes.extend([i] * choice['votes'][i])
            choice['votes'] = votes

        # Compute the median, the number of better and worse vote.
        for _, choice in choices.items():
            choice_compute(choice)

        # Apply the grade for each choice
        for choice in choices:
            if choices[choice]['median'] == 0:
                results[choice]['grade'] = "To reject"
            elif choices[choice]['median'] == 1:
                results[choice]['grade'] = "Poor"
            elif choices[choice]['median'] == 2:
                results[choice]['grade'] = "Acceptable"
            elif choices[choice]['median'] == 3:
                results[choice]['grade'] = "Fair"
            elif choices[choice]['median'] == 4:
                results[choice]['grade'] = "Good"
            elif choices[choice]['median'] == 5:
                results[choice]['grade'] = "Very Good"
            elif choices[choice]['median'] == 6:
                results[choice]['grade'] = "Excellent"

            if choices[choice]['better'] > choices[choice]['worse']:
                results[choice]['grade'] += "+"
            else:
                results[choice]['grade'] += "-"

        # Sort the vote to etablish the ranks
        ranks = rank_choices(choices, ballots_count)
        for choice in results:
            results[choice]['rank'] = ranks[choice]


        # Store the results
        results_db = []
        for choice, result in results.items():
            results_db.append((poll['uid'], choice, ";".join([str(rank) for rank in result['rank']]) if isinstance(result['rank'], list) else str(result['rank']), result['grade'], ";".join([str(percentage) for percentage in result['percentages']]), result['ballots']))

        get_db().executemany("INSERT INTO results (poll, choice, rank, grade, percentages, ballots) VALUES (?, ?, ?, ?, ?, ?)", results_db)

        # Destroy the ballots
        get_db().execute('DELETE FROM ballots WHERE poll = ?', [poll['uid']])

    else:
        for result in results_db:
            results[result['choice']] = {'rank' : int(result['rank']) if ';' not in result['rank'] else [int(vote) for vote in result['rank'].split(';')], 'grade': result['grade'], 'percentages': [int(percentage) for percentage in result['percentages'].split(';')], 'ballots': result['ballots']}

    return results

