'''class to watch for new games and prepare the data
when game is over save it and remove from games under watch'''
import json
import requests
import discord

import config


class OngoingNotifier:
    '''class to hold the ongoing match objects'''

    def __init__(self, bot, map_fetcher, logger):
        self.bot = bot
        self.logger = logger
        self.map_fetcher = map_fetcher
        self.games = {}
        self.messages = {}
        self.closed_matches = []
        self.updated_matches = []
        self.finished_matches = []
        self.stats_link = config.STATS_URL
        self.match_url = config.MATCH_URL

    def updater(self, hubs):
        '''Main function to process each of the hubs for live games'''
        for match in self.closed_matches:
            del self.games[match]
            del self.messages[match]

        self.closed_matches = []
        for hub_name, hub_data in hubs.items():
            hub_url = self.match_url.format(hub=hub_data["guid"])
            response = requests.get(hub_url, timeout=5)

            if (len(response.text) > 0) and (response.text is not None):

                try:
                    matches_payload = json.loads(response.text)

                    for match in matches_payload["payload"]:
                        if match["id"] in self.games:

                            self.updated_matches.append(match["id"])

                            self.messages[match["id"]] = self.games[match["id"]].update_game_status(
                                match)

                        else:

                            self.updated_matches.append(match["id"])
                            self.games[match["id"]] = Game(match, hub_name)
                            if "summaryResults" in match.keys():
                                self.messages[match["id"]] = self.games[match["id"]].update_game_status(
                                    match)
                            else:
                                self.messages[match["id"]] = self.games[match["id"]].build_message_contents(
                                    "Starting")

                except Exception as e:
                    self.logger.error(f'{hub_name} has an issue in onging notifier, updater {e}')
                    print(hub_name, e)

    def check_finished_matches(self):
        '''logic to check if match is finished and close out'''

        for finished_match_id, game in self.games.items():

            if finished_match_id not in self.updated_matches:

                try:
                    response = requests.get(self.stats_link + finished_match_id, timeout=5)
                    finished_match_data = json.loads(response.text)

                    if len(finished_match_data) > 0:
                        self.messages[finished_match_id] = self.games[finished_match_id].finished_match_update(
                            finished_match_data)

                    stored_in_db = self.map_fetcher.finished_match_processor(finished_match_id)

                    if stored_in_db:
                        self.closed_matches.append(finished_match_id)

                except Exception as e:
                    self.logger.error(f'{game.hub_name} has an issue in onging notifier, check_finished_matches, match id {finished_match_id} {e}')

        self.updated_matches = []


class Game:
    '''Class which holds the game info, makes the message contents with embeds'''

    def __init__(self, game_payload, hub_name):
        '''Initialise a new game instance'''
        self.id = game_payload["id"]
        self.hub = game_payload["entity"]["name"]
        self.hub_name = hub_name
        self.faction1 = self.team_processor(game_payload["teams"]["faction1"])
        self.faction2 = self.team_processor(game_payload["teams"]["faction2"])
        self.server = game_payload["voting"]["location"]["pick"]
        self.map_id = game_payload["voting"]["map"]["pick"][0]

        self.faction1_score = 0
        self.faction2_score = 0

        self.map_name = "Errored - id is" + str(self.map_id)

        for map_dict in game_payload["maps"]:
            if self.map_id == map_dict["game_map_id"]:
                self.map_name = map_dict["name"]
                self.class_name = map_dict["class_name"]
                self.map_img = map_dict["image_sm"]

    def team_processor(self, team_data):
        '''function to make teams lists and add in level emojis to list'''

        faceit_levels = {1: "<:level1:741416090407665844>",
                         2: "<:level2:741416090076315669>",
                         3: "<:level3:741416090034372670>",
                         4: "<:level4:741416090420379738>",
                         5: "<:level5:741416090353008720>",
                         6: "<:level6:741416090407665854>",
                         7: "<:level7:741416090298482770>",
                         8: "<:level8:741416090617511956>",
                         9: "<:level9:741416090483032245>",
                         10: "<:level10:741416090516586526>"}

        team = {}
        team["team_name"] = team_data["name"]
        team["players"] = ""

        for player in team_data["roster"]:
            team["players"] = team["players"] + \
                faceit_levels[player["gameSkillLevel"]] + \
                " " + player["nickname"] + "\n"

        return team

    def finished_match_update(self, finished_match_data):
        '''function to set final score of game and make final message'''

        self.faction1_score = finished_match_data[0]["teams"][0]["c5"]
        self.faction2_score = finished_match_data[0]["teams"][1]["c5"]

        return self.build_message_contents("Finished")

    def update_game_status(self, game_payload):
        '''function to update score of ongoing game'''

        if "summaryResults" in game_payload.keys():
            if "factions" in game_payload["summaryResults"].keys():
                self.faction1_score = game_payload["summaryResults"]["factions"]["faction1"]["score"]
                self.faction2_score = game_payload["summaryResults"]["factions"]["faction2"]["score"]

        return self.build_message_contents("Ongoing")

    def build_message_contents(self, match_status):
        '''function to build message and embeds'''

        embeded_message = discord.Embed(title=match_status + " match: ",
                                        description="# " + self.map_name + "\n On " + self.hub, color=0xff5500)
        embeded_message.set_thumbnail(url=self.map_img)

        score_string = f"** {self.faction1_score} - {self.faction2_score} **"

        embeded_message.add_field(
            name="`" + self.faction1["team_name"] + "`", value=self.faction1["players"], inline=True)
        embeded_message.add_field(name=score_string, value="", inline=True)
        embeded_message.add_field(
            name="`" + self.faction2["team_name"] + "`", value=self.faction2["players"], inline=True)
        embeded_message.add_field(
            name=" ", value="[Summary](https://www.faceit.com/en/cs2/room/" + self.id + ")")

        return embeded_message
