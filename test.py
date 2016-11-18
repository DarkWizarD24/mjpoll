# coding: utf-8

import os
import mjpoll
import unittest
import tempfile
from datetime import datetime, timedelta
import collections


def equals(a, b):
    if not isinstance(a, collections.Iterable) or not isinstance(b, collections.Iterable) or isinstance(a, unicode) or isinstance(b, unicode) or isinstance(a, str) or isinstance(b, str):
        return a == b
    
    if len(a) != len(b):
        return False
    
    if isinstance(a, dict) or isinstance(b, dict):
        return equals(sorted(a.items()), sorted(b.items()))
    
    return all([equals(a, b) for a, b in zip(a,b)])


class MJPollTestCase(unittest.TestCase):

    def setUp(self):
        self.db_fd, mjpoll.app.config['DATABASE'] = tempfile.mkstemp()
        mjpoll.app.config['TESTING'] = True
        self.app = mjpoll.app.test_client()
        with mjpoll.app.app_context():
            mjpoll.init_db()

    def tearDown(self):
        os.close(self.db_fd)
        os.unlink(mjpoll.app.config['DATABASE'])

    def add_poll_with_a_ballot(self):
        with mjpoll.app.app_context():
            poll_uid = mjpoll.data.insert_poll(title='Red or Blue ?', message='What pill is the best ?', choices=['Blue one', 'Red One'], end_date=datetime.now() + timedelta(3), owner='Bob')
            mjpoll.data.add_update_ballot(voter='Bob', poll=poll_uid, choices={1: 2, 2: 5})
            return poll_uid

    def test_1_db_1_insert_poll(self):
        with mjpoll.app.app_context():
            date = datetime.now()
            poll_uid = mjpoll.data.insert_poll(title='Rabbit or Bunny ?', message='What do we eat tonight ?', choices=['Rabbit (https://en.wikipedia.org/wiki/Rabbit)', 'Bunny (https://en.wikipedia.org/wiki/Bunny)'], end_date=date, owner='Bob')
            
            # Check poll creation
            c = mjpoll.data.get_db().cursor()
            c.execute('SELECT * from polls')
            expected = (poll_uid, u'Rabbit or Bunny ?', u'What do we eat tonight ?', date, 'Bob')
            reality = c.fetchall()[0]
            assert equals(expected, reality)
            
            # Check choices creation
            c = mjpoll.data.get_db().cursor()
            c.execute('SELECT * from choices')
            expected = [(1, poll_uid, u'Rabbit (https://en.wikipedia.org/wiki/Rabbit)'), (2, poll_uid, u'Bunny (https://en.wikipedia.org/wiki/Bunny)')]
            reality = c.fetchall()
            assert equals(expected, reality)
            
            return poll_uid, date
                
    def test_1_db_2_add_update_ballot(self):
        with mjpoll.app.app_context():
            # Test ballot add
            poll_uid = self.add_poll_with_a_ballot()
                    
            # Check ballots creation
            c = mjpoll.data.get_db().cursor()
            c.execute('SELECT * from ballots')
            expected = [(u'Bob', poll_uid, 1, 2), (u'Bob', poll_uid, 2, 5)]
            reality = c.fetchall()
            assert equals(expected, reality)

            # Test ballot update
            mjpoll.data.add_update_ballot(voter='Bob', poll=poll_uid, choices={1: 3, 2: 4})
                    
            # Check ballots update
            c = mjpoll.data.get_db().cursor()
            c.execute('SELECT * from ballots')
            expected = [(u'Bob', poll_uid, 1, 3), (u'Bob', poll_uid, 2, 4)]
            reality = c.fetchall()
            assert equals(expected, reality)
            
            # Test ballots update of a closed poll
            
            # Start by setup the end date in the past
            c.execute('UPDATE polls SET end_date = ? WHERE uid = ?', [datetime.now() - timedelta(3), poll_uid])
            
            # Try to update
            mjpoll.data.add_update_ballot(voter='Bob', poll=poll_uid, choices={1: 5, 2: 1})
            
            # Check that nothing changed
            c = mjpoll.data.get_db().cursor()
            c.execute('SELECT * from ballots')
            reality = c.fetchall()
            assert equals(expected, reality)
            
            return poll_uid

    def test_1_db_3_get_poll(self):
        poll_uid, date = self.test_1_db_1_insert_poll()
        
        with mjpoll.app.app_context():
           expected = {'message': u'What do we eat tonight ?', 'choices': [{'text': u'Rabbit (https://en.wikipedia.org/wiki/Rabbit)', 'poll': poll_uid, 'id': 1}, {'text': u'Bunny (https://en.wikipedia.org/wiki/Bunny)', 'poll': poll_uid, 'id': 2}], 'uid': poll_uid, 'end_date': date, 'title': u'Rabbit or Bunny ?', 'closed': True, 'owner': 'Bob'}
           reality =  mjpoll.data.get_poll(poll_uid)
           assert equals(expected, reality)
        
    def test_1_db_4_get_voter_ballot(self):
        poll_uid = self.add_poll_with_a_ballot()
        
        with mjpoll.app.app_context():
            expected = {1: 2, 2: 5}
            reality = mjpoll.data.get_voter_ballot('Bob', poll_uid)
            assert equals(expected, reality)
    
    
    def test_1_db_5_get_results(self):
        with mjpoll.app.app_context():
            # Create a poll with lot of votes
            poll_uid = mjpoll.data.insert_poll(title='Tennessee Capital', message='Which city must be the capital of Tennessee ?', choices=['Memphis', 'Nashville', 'Chattanooga', 'Knoxville'], end_date=datetime.now() + timedelta(3), owner='Bob')
            for i in range(84):
                mjpoll.data.add_update_ballot(voter='Memphis' + str(i), poll=poll_uid, choices={1: 6, 2: 4, 3: 3, 4: 3})
            for i in range(52):
                mjpoll.data.add_update_ballot(voter='Nashville' + str(i), poll=poll_uid, choices={1: 3, 2: 6, 3: 4, 4: 4})
            for i in range(30):
                mjpoll.data.add_update_ballot(voter='Chattanooga' + str(i), poll=poll_uid, choices={1: 3, 2: 4, 3: 6, 4: 5})
            for i in range(34):
                mjpoll.data.add_update_ballot(voter='Knoxville' + str(i), poll=poll_uid, choices={1: 3, 2: 4, 3: 5, 4: 6})
                        
            # Read results before the vote is closed
            assert equals(mjpoll.data.get_results(mjpoll.data.get_poll(poll_uid)), None)
            
            # Close the vote
            c = mjpoll.data.get_db().cursor()
            c.execute('UPDATE polls SET end_date = ? WHERE uid = ?', [datetime.now() - timedelta(3), poll_uid])
            
            # Read result not computed
            expected = {1: {'rank': 4, 'grade': 'Fair+', 'percentages': [0, 0, 0, 58, 00, 00, 42], 'ballots': 200},
                        2: {'rank': 1, 'grade': 'Good+', 'percentages': [0, 0, 0, 00, 74, 00, 26], 'ballots': 200},
                        3: {'rank': 3, 'grade': 'Good-', 'percentages': [0, 0, 0, 42, 26, 17, 15], 'ballots': 200},
                        4: {'rank': 2, 'grade': 'Good-', 'percentages': [0, 0, 0, 42, 26, 15, 17], 'ballots': 200}}
            reality = mjpoll.data.get_results(mjpoll.data.get_poll(poll_uid))
            assert equals(expected, reality)
            
            # Check if ballots details are erased
            assert equals(mjpoll.data.get_voter_ballot('Memphis12', poll_uid), None)
            
            # Erase the ballots to be check if the results where cached
            c.execute('DELETE FROM ballots')
            
            # Read the results again (this time they are cached)
            reality = mjpoll.data.get_results(mjpoll.data.get_poll(poll_uid))
            assert equals(expected, reality)
    
    def test_1_db_6_get_results_ties(self):
        with mjpoll.app.app_context():
            # Create a poll with lot of votes
            poll_uid = mjpoll.data.insert_poll(title='Tennessee Capital', message='Which city must be the capital of Tennessee ?', choices=['Memphis', 'Nashville', 'Chattanooga', 'Knoxville'], end_date=datetime.now() + timedelta(3), owner='Bob')
            for i in range(10):
                mjpoll.data.add_update_ballot(voter='Memphis' + str(i), poll=poll_uid, choices={1: 6, 2: 0, 3: 0, 4: 0})
            for i in range(10):
                mjpoll.data.add_update_ballot(voter='Nashville' + str(i), poll=poll_uid, choices={1: 0, 2: 6, 3: 0, 4: 0})
            for i in range(10):
                mjpoll.data.add_update_ballot(voter='Chattanooga' + str(i), poll=poll_uid, choices={1: 0, 2: 0, 3: 6, 4: 0})
            for i in range(10):
                mjpoll.data.add_update_ballot(voter='Knoxville' + str(i), poll=poll_uid, choices={1: 0, 2: 0, 3: 1, 4: 6})
     
            # Close the vote
            c = mjpoll.data.get_db().cursor()
            c.execute('UPDATE polls SET end_date = ? WHERE uid = ?', [datetime.now() - timedelta(3), poll_uid])
            
            # Read result
            expected = {1: {'percentages': [75, 0, 0, 0, 0, 0, 25], 'grade': 'To reject+', 'ballots': 40, 'rank': [2, 3, 4]},
                        2: {'percentages': [75, 0, 0, 0, 0, 0, 25], 'grade': 'To reject+', 'ballots': 40, 'rank': [2, 3, 4]},
                        3: {'percentages': [50, 25, 0, 0, 0, 0, 25], 'grade': 'Poor-', 'ballots': 40, 'rank': 1},
                        4: {'percentages': [75, 0, 0, 0, 0, 0, 25], 'grade': 'To reject+', 'ballots': 40, 'rank': [2, 3, 4]}}
            reality = mjpoll.data.get_results(mjpoll.data.get_poll(poll_uid))
            assert equals(expected, reality) 
    
    def test_1_db_7_get_results_ties_2(self):
        with mjpoll.app.app_context():
            # Create a poll with lot of votes
            poll_uid = mjpoll.data.insert_poll(title='A,B or C ?', message='Which letter is the best ?', choices=['A', 'B', 'C'], end_date=datetime.now() + timedelta(3), owner='Bob')
            for i in range(20):
                mjpoll.data.add_update_ballot(voter='A' + str(i), poll=poll_uid, choices={1: 6, 2: 5, 3: 5})
            for i in range(25):
                mjpoll.data.add_update_ballot(voter='B' + str(i), poll=poll_uid, choices={1: 5, 2: 6, 3: 6})
            for i in range(5):
                mjpoll.data.add_update_ballot(voter='C' + str(i), poll=poll_uid, choices={1: 6, 2: 6, 3: 6})
            for i in range(25):
                mjpoll.data.add_update_ballot(voter='D' + str(i), poll=poll_uid, choices={1: 4, 2: 4, 3: 4})
            for i in range(25):
                mjpoll.data.add_update_ballot(voter='E' + str(i), poll=poll_uid, choices={1: 3, 2: 3, 3: 3})
                
            # Close the vote
            c = mjpoll.data.get_db().cursor()
            c.execute('UPDATE polls SET end_date = ? WHERE uid = ?', [datetime.now() - timedelta(3), poll_uid])
            
            # Read result
            expected = {1: {'percentages': [0, 0, 0, 25, 25, 25, 25], 'grade': 'Very Good-', 'ballots': 100, 'rank': 3},
                        2: {'percentages': [0, 0, 0, 25, 25, 20, 30], 'grade': 'Very Good-', 'ballots': 100, 'rank': [1, 2]},
                        3: {'percentages': [0, 0, 0, 25, 25, 20, 30], 'grade': 'Very Good-', 'ballots': 100, 'rank': [1, 2]}}
            reality = mjpoll.data.get_results(mjpoll.data.get_poll(poll_uid))
            assert equals(expected, reality) 
    
    def test_2_view_1_ballot_or_results(self):
        # Check what happens if you request a non existing poll
        rv = self.app.get('/fjzeghezgh')
        #assert b'This poll do not exists.' in rv.data
         
        # Check to load an open poll with votes in it
        poll_uid = self.add_poll_with_a_ballot()
        rv = self.app.get('/' + poll_uid)
        
        #TODO assert b'<input type="radio" name="choice1" value="3" checked />' in rv.data
        #TODO assert b'<input type="radio" name="choice1" value="4" />' in rv.data
        
        #TODO finish

        
def delete_all_data_db():
    with mjpoll.app.app_context():
        c = mjpoll.data.get_db().cursor()
        c.execute('DELETE FROM ballots')
        c.execute('DELETE FROM results')
        c.execute('DELETE FROM choices')
        c.execute('DELETE FROM polls')
        mjpoll.data.get_db().commit() 
 
 
def inject_data_closed_poll():
    """Call this function to add a closed poll with results into the database"""
    with mjpoll.app.app_context():
        # Create a poll with lot of votes
        poll_uid = mjpoll.data.insert_poll(title='Tennessee Capital', message='Which city must be the capital of Tennessee ?', choices=['Memphis', 'Nashville', 'Chattanooga', 'Knoxville'], end_date=datetime.now() + timedelta(3), owner='Bob')
        poll = mjpoll.data.get_poll(poll_uid)
        
        memphis = [choice['id'] for choice in poll['choices'] if choice['text'] == 'Memphis'][0]
        nashville = [choice['id'] for choice in poll['choices'] if choice['text'] == 'Nashville'][0]
        chattanooga = [choice['id'] for choice in poll['choices'] if choice['text'] == 'Chattanooga'][0]
        knoxville = [choice['id'] for choice in poll['choices'] if choice['text'] == 'Knoxville'][0]
        
        for i in range(10):
            mjpoll.data.add_update_ballot(voter='Memphis' + str(i), poll=poll_uid, choices={memphis: 6, nashville: 0, chattanooga: 0, knoxville: 0})
        for i in range(10):
            mjpoll.data.add_update_ballot(voter='Nashville' + str(i), poll=poll_uid, choices={memphis: 0, nashville: 6, chattanooga: 0, knoxville: 0})
        for i in range(10):
            mjpoll.data.add_update_ballot(voter='Chattanooga' + str(i), poll=poll_uid, choices={memphis: 0, nashville: 0, chattanooga: 6, knoxville: 0})
        for i in range(10):
            mjpoll.data.add_update_ballot(voter='Knoxville' + str(i), poll=poll_uid, choices={memphis: 0, nashville: 0, chattanooga: 1, knoxville: 6})
 
        # Close the vote
        c = mjpoll.data.get_db().cursor()
        c.execute('UPDATE polls SET end_date = ? WHERE uid = ?', [datetime.now() - timedelta(3), poll_uid])
        
        mjpoll.data.get_results(mjpoll.data.get_poll(poll_uid))
        
        mjpoll.data.get_db().commit() 
        
        print "poll added with uid: " + str(poll_uid)
         
 
def inject_data_closed_poll_2():
    """Call this function to add a closed poll with results into the database"""
    with mjpoll.app.app_context():
        # Create a poll with lot of votes
        poll_uid = mjpoll.data.insert_poll(title='Tennessee Capital', message='Which city must be the capital of Tennessee ?', choices=['Memphis', 'Nashville', 'Chattanooga', 'Knoxville'], end_date=datetime.now() + timedelta(3), owner='Bob')
        poll = mjpoll.data.get_poll(poll_uid)
        
        memphis = [choice['id'] for choice in poll['choices'] if choice['text'] == 'Memphis'][0]
        nashville = [choice['id'] for choice in poll['choices'] if choice['text'] == 'Nashville'][0]
        chattanooga = [choice['id'] for choice in poll['choices'] if choice['text'] == 'Chattanooga'][0]
        knoxville = [choice['id'] for choice in poll['choices'] if choice['text'] == 'Knoxville'][0]
        
        for i in range(84):
            mjpoll.data.add_update_ballot(voter='Memphis' + str(i), poll=poll_uid, choices={memphis: 6, nashville: 4, chattanooga: 3, knoxville: 3})
        for i in range(52):
            mjpoll.data.add_update_ballot(voter='Nashville' + str(i), poll=poll_uid, choices={memphis: 3, nashville: 6, chattanooga: 4, knoxville: 4})
        for i in range(30):
            mjpoll.data.add_update_ballot(voter='Chattanooga' + str(i), poll=poll_uid, choices={memphis: 3, nashville: 4, chattanooga: 6, knoxville: 5})
        for i in range(34):
            mjpoll.data.add_update_ballot(voter='Knoxville' + str(i), poll=poll_uid, choices={memphis: 3, nashville: 4, chattanooga: 5, knoxville: 6})
 
        # Close the vote
        c = mjpoll.data.get_db().cursor()
        c.execute('UPDATE polls SET end_date = ? WHERE uid = ?', [datetime.now() - timedelta(3), poll_uid])
        
        mjpoll.data.get_results(mjpoll.data.get_poll(poll_uid))
        
        mjpoll.data.get_db().commit() 
        
        print "poll added with uid: " + str(poll_uid)
        
          
def inject_data_open_poll():
    """Call this function to add an open poll into the database"""
    with mjpoll.app.app_context():
        # Create a poll with lot of votes
        poll_uid = mjpoll.data.insert_poll(title='Tennessee Capital', message='Which city must be the capital of Tennessee ?\n\n * aaaa \n * bbbb', choices=['**Memphis** (https://fr.wikipedia.org/wiki/Memphis_(Tennessee))', '*Nashville* [lol](https://fr.wikipedia.org/wiki/Nashville)', 'Chattanooga (https://fr.wikipedia.org/wiki/Chattanooga)', 'Knoxville (https://fr.wikipedia.org/wiki/Knoxville_(Tennessee))'], end_date=datetime.now() + timedelta(3), owner='Bob')
        print "poll added with uid: " + str(poll_uid)
        
        
def inject_data_open_poll_with_ballots():
    """Call this function to add an open poll into the database"""
    with mjpoll.app.app_context():
        # Create a poll with lot of votes
        poll_uid = mjpoll.data.insert_poll(title='Tennessee Capital', message='Which city must be the capital of Tennessee ?', choices=['Memphis', 'Nashville', 'Chattanooga', 'Knoxville'], end_date=datetime.now() + timedelta(3), owner='Bob')
        
        poll = mjpoll.data.get_poll(poll_uid)
        
        memphis = [choice['id'] for choice in poll['choices'] if choice['text'] == 'Memphis'][0]
        nashville = [choice['id'] for choice in poll['choices'] if choice['text'] == 'Nashville'][0]
        chattanooga = [choice['id'] for choice in poll['choices'] if choice['text'] == 'Chattanooga'][0]
        knoxville = [choice['id'] for choice in poll['choices'] if choice['text'] == 'Knoxville'][0]
        
        for i in range(84):
            mjpoll.data.add_update_ballot(voter='Memphis' + str(i), poll=poll_uid, choices={memphis: 6, nashville: 4, chattanooga: 3, knoxville: 3})
        for i in range(52):
            mjpoll.data.add_update_ballot(voter='Nashville' + str(i), poll=poll_uid, choices={memphis: 3, nashville: 6, chattanooga: 4, knoxville: 4})
        for i in range(30):
            mjpoll.data.add_update_ballot(voter='Chattanooga' + str(i), poll=poll_uid, choices={memphis: 3, nashville: 4, chattanooga: 6, knoxville: 5})
        for i in range(34):
            mjpoll.data.add_update_ballot(voter='Knoxville' + str(i), poll=poll_uid, choices={memphis: 3, nashville: 4, chattanooga: 5, knoxville: 6})
        
        print "poll added with uid: " + str(poll_uid)
        
if __name__ == '__main__':
    unittest.main()


