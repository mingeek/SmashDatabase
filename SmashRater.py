import json
import glicko2
import re
import operator
import Queue
#from challonge import participants, matches, tournaments
import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning
import WriteBrackets
import MySQLdb as mariadb
import string
import re
import pysmash
import math
from dateutil import parser

def prompt(type, value):
	return raw_input("Retrieved "+type+": "+value+". Press Enter if this is correct or type the correct value:\n\t") or value

def strip_tag(tag):
	return "".join(c for c in tag.strip() if c.isalnum()).lower()

def stripped_tag_by_id_challonge(player_id, data):
	for participant in data['participants']:
		p = participant['participant']
		if p['id'] == player_id:
			n = p['display_name']
			return strip_tag((n.rsplit('|', 1) if '|' in n else (None, n))[1])
	raise Exception("Error: Unable to find participant.")

def stripped_tag_by_id_smashgg(player_id, players):
	for p in players:
		
		if int(p['entrant_id']) == int(player_id):
			n = p['tag']
			return strip_tag((n.rsplit('|', 1) if '|' in n else (None, n))[1])
	raise Exception("Error: Unable to find participant.")

def build_display_name(sponsor, tag):
	return sponsor+ ' | ' +tag if sponsor else tag

db_connection = mariadb.connect(
		user="mingee",
		passwd="",
		db="MeleeData",
		use_unicode = True,
		charset = "utf8"
	)
db_cursor = db_connection.cursor()

def strip_num(tournament_name):
	series_parts = t['name'].rsplit(None, 1)
	if len(series_parts) == 2 and all(c in '0123456789XVI' for c in series_parts[1]):
		series = series_parts[0]
	else:
		series = ''
	return series

with open("data/brackets.txt", "r") as f:
    url_list = [line.strip() for line in f if line.strip()]

for url in url_list:
	matches = {}
	players = {}

	url = url.lower().replace('http://', '').replace('https://', '')

	t = {}

	hostname_parts = url.split('/')[0].split('.')
	print hostname_parts
	host = hostname_parts[-2]
	if host == "challonge":
		t['id'] = (hostname_parts[0] + '-' + url.split('/')[1]).replace('challonge-', '').strip()
	elif host == "smash":
		t['id'] = url.split("/tournament/")[1].split("/")[0]
		host = "smashgg"
	else:
		print "BAD URL"
		continue

	t['host'] = host

	print("Loading tournament: " + t['id'])

	# skip existing
	db_cursor.execute("SELECT 1 FROM tournaments WHERE id = %s LIMIT 1", [t['id']])
	if db_cursor.fetchone() is not None:
		print("Tournament already saved in database; skipping.\n")
		continue

	if host == "challonge":
		data = {}
		try:
			for data_type, subpath in [(type, t['id']+path) for type, path in [('tournament',''),('matches','/matches'),('participants','/participants')]]:
				uri = 'https://api.challonge.com/v1/tournaments/'+subpath+'.json'
				print("Contacting API at %s..." % uri)
				data[data_type] = requests.get(uri+'?api_key=XBFwcbaWSvrfHiaNONNgwyfPo8LrYozALwIWfkBd').json()
				if 'errors' in data[data_type]:
					raise Exception(data[data_type]['errors'][0])
		except Exception as e:
			print("Error accessing %s: %s" % (uri, e))
			continue

		tournament = data['tournament']['tournament']
		t['name'] = tournament['name']
		t['date'] = tournament['started_at'].split('T')[0]
		t['series'] = strip_num(t['name'])
		t['entrants'] = tournament['participants_count']

		if t['entrants'] != len(data['participants']):
			print("Error: Only " + len(data['participants']) + " out of " + t['entrants'] + " entrants have data.")
			continue

		for player in data['participants']:
			display_name = player['participant']['name']
			sponsor, tag = display_name.rsplit('|', 1) if '|' in display_name else (None, display_name)
			players[strip_tag(tag)] = {'sponsor': sponsor.strip() if sponsor else None}
	
	elif host == "smashgg":

		#Smash.gg wrapper
		smash = pysmash.SmashGG()

		tournament_name = url.split("/tournament/")[1].split("/")[0]
		tournament = {}
		#TO DO: Ann Arbor should be replaced by region use tourney information to find venue address and get State from there. 

		ggplayers = smash.tournament_show_players(tournament_name, 'melee-singles')
		t['name'] = tournament_name
		t['date'] = ''#TO DO tournament['started_at'].split('T')[0]
		t['series'] = strip_num(tournament_name)
		t['entrants'] = len(players)

		for player in ggplayers:
			players[strip_tag(player['tag'])] = {'sponsor': player['prefix'].strip() if 'prefix' in player else None}

	if len(players) <= 4:
		print "Double Elimination Tournament requires at least 5 entrants"
		continue

	db_cursor.execute("""
		INSERT INTO tournaments (id,      host,      name,      series,      date,     location)
		VALUES                  (%s,      %s,        %s,        %s,          %s,       'MI')
		""",                    (t['id'], t['host'], t['name'], t['series'], t['date']))
	print "Retrieved tournament data:"
	print json.dumps(t, indent=2)

	db_cursor.execute("""
		SELECT tag, sponsor, rating, rating_deviation, volatility
		FROM players
		WHERE tag IN (%s)
		""" % ','.join(['%s' for tag in players.keys()]), players.keys())


	for tag, sponsor, rating, rating_deviation, volatility in db_cursor.fetchall():
		players[tag]['glicko2'] = glicko2.Player(rating, rating_deviation, volatility)


	for tag, p in players.iteritems():
		if 'glicko2' not in p:
			p['new'] = True
			g2 = p['glicko2'] = glicko2.Player()

			db_cursor.execute("""
				INSERT INTO players (tag, sponsor,      rating,    rating_deviation, volatility)
				VALUES              (%s,  %s,           %s,        %s,               %s)
				""",                (tag, p['sponsor'], g2.rating, g2.rd,            g2.vol))

	# Split this into another function 
	

	if host == "smashgg":
		sets = smash.tournament_show_sets(tournament_name, 'melee-singles')
		winners_set_count = losers_set_count = 0
		for match in sets:
			#TODO: split this nigga
			round_num = match['short_round_text'][1:]
			if round_num.isdigit():
				if match['short_round_text'][0] == "W":
					if winners_set_count < int(round_num):
						winners_set_count += 1
				elif match['short_round_text'][0] == "L":
					if losers_set_count < int(round_num):
						losers_set_count += 1
		tournament['winners_rounds'] = winners_set_count
		tournament['losers_rounds'] = losers_set_count

	elif host == "challonge":
		tournament['winners_rounds'] = tournament['losers_rounds'] = 0
		for match in data['matches']:
			round = match['match']['round']
			if round > 0:
				if round > tournament['winners_rounds']:
					tournament['winners_rounds'] = round
			else:
				round = abs(round)
				if round > tournament['losers_rounds']:
					tournament['losers_rounds'] = round
	if host == "challonge":
		score_format = re.compile("\d+-\d+")
		for match in data['matches']:
			match = match['match']

			# scores in the wrong format are DQs and do not count for rating
			if not score_format.match(match['scores_csv']):
				continue

			p1_name = stripped_tag_by_id_challonge(match['player1_id'], data)
			p2_name = stripped_tag_by_id_challonge(match['player2_id'], data)

			p1_score, p2_score = match['scores_csv'].split('-')
			p1_score = int(p1_score)
			p2_score = int(p2_score)

			m = {}
			m['winner_tag'] = stripped_tag_by_id_challonge(match['winner_id'], data)
			m['loser_tag'] = stripped_tag_by_id_challonge(match['loser_id'], data)
			m['best_of'] = 2*max(p1_score, p2_score) - 1
			m['loser_wins'] = min(p1_score, p2_score)
			m['is_losers'] = match['round'] < 0
			m['round_number'] = match['round']

		#TODO - Make Challonge Recognize Titles (WSF/WF/LF/GF)
			m['title'] = 'TBD'

			matches[parser.parse(match['completed_at'])] = m
	elif host == "smashgg":

		GF = False
		for match in sets:
			print match
			games_counted = False
			if 'p1_score' in match:
				games_counted = True
				p1_score = match['entrant_1_score']
				p2_score = match['entrant_2_score']
			
			#TODO make a pair
			match_type = match['short_round_text'][0]
			round_text = match['short_round_text'][1:]

			if match_type == 'L':
				if round_text.isdigit():
					round_number = int(round_text)
				elif round_text == 'QF':
					round_number = tournament['losers_rounds']+1
				elif round_text == 'SF':
					round_number = tournament['losers_rounds']+2
				elif round_text == 'F':
					round_number = tournament['losers_rounds']+3
			elif match_type == 'W':
				if round_text.isdigit():
					round_number = int(round_text)
				elif round_text == 'QF':
					round_number = tournament['winners_rounds']+1
				elif round_text == 'SF':
					round_number = tournament['winners_rounds']+2
				elif round_text == 'F':
					round_number = tournament['winners_rounds']+3				
			else:
				if GF:
					round_number = tournament['winners_rounds']+5
				else:
					round_number = tournament['winners_rounds']+4

			m = {}
			m['winner_tag'] = stripped_tag_by_id_smashgg(match['winner_id'], ggplayers)
			m['loser_tag'] = stripped_tag_by_id_smashgg(match['loser_id'], ggplayers)
			m['best_of'] = 2*max(p1_score, p2_score) - 1 if games_counted else 1
			m['loser_wins'] = min(p1_score, p2_score) if games_counted else 0
			m['is_losers'] = match_type == 'L'
			m['round_number'] = round_number
			m['title'] = match['short_round_text']
			matches[parser.parse(match['completed_at'])] = m
			print match
	for time in sorted(matches.keys()):
		m = matches[time]

		temp = {'rating': players[m['winner_tag']]['glicko2'].rating, 'rd': players[m['winner_tag']]['glicko2'].rd}
		players[m['winner_tag']]['glicko2'].update_player([[True,  players[m['loser_tag']]['glicko2'].rating, players[m['loser_tag']]['glicko2'].rd]])
		players[m['loser_tag'] ]['glicko2'].update_player([[False, temp['rating'],                            temp['rd']]])

		m['winner_rating'] = players[m['winner_tag']]['glicko2'].rating
		m['loser_rating']  = players[m['loser_tag'] ]['glicko2'].rating


		db_cursor.execute("""
			INSERT INTO sets (tournament_id, winner_tag,      winner_rating,      loser_tag,      loser_rating,      best_of,      loser_wins,      round_number,      is_losers,      title)
			VALUES           (%s,            %s,              %s,                 %s,             %s,                %s,           %s,              %s,                %s,            %s)
			""",             (t['id'],       m['winner_tag'], m['winner_rating'], m['loser_tag'], m['loser_rating'], m['best_of'], m['loser_wins'], m['round_number'], m['is_losers'], m['title']))

	for tag, p in players.iteritems():
		g2 = p['glicko2']
		db_cursor.execute("""
			UPDATE players SET sponsor=%s,   rating=%s, rating_deviation=%s, volatility=%s WHERE tag=%s
			""",              (p['sponsor'], g2.rating, g2.rd,               g2.vol,             tag))

		if 'new' in p:
			print "New player: (%s) %s" % (g2.rating, build_display_name(p['sponsor'], tag))
		else:
			print "Updated: (%s) %s"    % (g2.rating, build_display_name(p['sponsor'], tag))

	db_connection.commit()

	print "Tournament written to database.\n"
