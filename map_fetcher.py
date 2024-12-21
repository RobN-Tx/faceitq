import json
import requests
import config
from mapcore_db import mapcore_db
import mapcore_functions as mapcorefunctions

MATCH_SEARCH_URL = "https://www.faceit.com/api/match/v2/match?entityId={hub}&entityType=hub&state=FINISHED&offset={offset}&limit=20"
SINGLE_MATCH_URL = "https://www.faceit.com/api/match/v2/match/"
STATS_URL = "https://api.faceit.com/stats/v1/stats/matches/"
HUBS_DICT = {
    "NA": "54e93df2-b867-4e8d-bf24-8769b03c5517",
    "EU": "05f970ad-b6a9-4740-89d1-a9fea46f7525",
    "NA Wingman": "b5254a71-c2b0-4912-8686-ed8f0474e22d",
    "EU Wingman": "913a69cb-be0e-466a-bb00-70ecf0301720",
    "SA": "8c9bf713-db99-4f40-97af-a0a47fded2c3",
}


class map_fetcher:

    def __init__(self, target_map, logger):
        print("hello Im the map fetcher and saver")
        self.matches = {}
        self.maps = {}
        self.target_map_string = target_map.lower()
        self.db = mapcore_db("MapCore_Dev.db")
        self.logger = logger

    def build_map_list(self):
        for hub in HUBS_DICT:
            self.hub_match_build(hub)

    def backfiller(self, games_to_fetch=20, start_offset=0):
        for hub in HUBS_DICT:
            self.hub_match_build(hub, games_to_fetch, start_offset)

    def hub_match_build(self, hub, games_to_fetch=20, start_offset=0):

        games_rounded = 20 * round(games_to_fetch / 20)
        i = 0
        while i <= games_rounded:
            offset = i + start_offset
            print(offset)
            self.fetch_maps(hub, offset)
            i = i + 20

    def fetch_maps(self, hub, run_offset):
        '''part of the backfiller'''
        target_url = MATCH_SEARCH_URL.format(hub=HUBS_DICT[hub], offset=str(run_offset))

        response = requests.get(target_url, timeout=5)



        try:  # (len(response.text) > 0) and (response.text is not None):
            matches_payload = json.loads(response.text)["payload"]

            for match in matches_payload:

                pre_existing = self.db.check_match(match["id"])

                if not pre_existing:
                    #print("exists")
                #else:
                    self.match_processor(match)
                
                map_guid = match["voting"]["map"]["pick"][0]
                map_name = [map_name for map_name in match["voting"]["map"]["entities"] if map_name["guid"] == map_guid][0]["name"]
                demo_storage_name = f'mapcore/{map_name}/{match["id"]}.dem.gz'
                
                demo_in_cloud = mapcorefunctions.blob_exists(demo_storage_name)
                
                #if not demo_in_cloud:
                    #print("demo in cloud")
                #else:
                    #mapcorefunctions.demo_download(match["demoURLs"][0], match["id"], map_name, self.logger)

        except Exception as e:
            error_string = f'Error fetch_maps, {e}'
            self.logger.error(error_string)

    def check_in_db(self, match_id):
        pre_existing = self.db.check_match(match_id)

        print(f"match {match_id} exists? {pre_existing}")

        return pre_existing

    def match_processor(self, match):
        '''not sure...'''
        map_guid = match["voting"]["map"]["pick"][0]
        map_name = [map_name for map_name in match["voting"]["map"]["entities"] if map_name["guid"] == map_guid][0]["name"].lower()
        class_name = [class_name for class_name in match["voting"]["map"]["entities"] if class_name["guid"] == map_guid][0]["class_name"].lower()

        if self.target_map_string == "*":
            processed = self.match_detailer(match)

        elif self.target_map_string in map_name or self.target_map_string in class_name:
            processed = self.match_detailer(match)

        return processed

    def finished_match_processor(self, finished_match_id):
        '''function to process a finished game and store'''
        target_url = SINGLE_MATCH_URL + finished_match_id
        pre_existing = False
        response = requests.get(target_url, timeout=5)

        return_bool = False
        try:
            if (len(response.text) > 0) and (response.text is not None):

                match_payload = json.loads(response.text)["payload"]

                if "voting" in match_payload.keys():
                    pre_existing = self.match_detailer(match_payload)

                    return_bool = pre_existing
                else:
                    # print("failed save gamne", match_payload)
                    return_bool = False
        except Exception as e:
            error_string = f'Error finished_match_processor, {e}'
            self.logger.error(error_string)

        return return_bool

    def match_detailer(self, match):
        '''function to detail the match, id map etc for db store'''
        match_data = {}

        match_id = match["id"]
        map_guid = match["voting"]["map"]["pick"][0]
        map_name = [map_name for map_name in match["voting"]["map"]["entities"] if map_name["guid"] == map_guid][0]["name"].lower()
        pre_existing = False
        # print(match.keys())
        if "demoURLs" in match.keys():
            stats = self.stats_processor(match_id)
            match_data = {
                "id": match_id,
                "hub": match["entity"]["name"],
                "map_guid": match["voting"]["map"]["pick"][0],
                "map_name": map_name,
                "class_name": [map_object for map_object in match["voting"]["map"]["entities"] if map_object["guid"] == map_guid][0]["class_name"].lower(),
                "room_link": "https://www.faceit.com/en/cs2/room/" + match_id,
                "stats": stats,
                "match_time": match["startedAt"],
                "image": [map_object for map_object in match["voting"]["map"]["entities"] if map_object["guid"] == map_guid][0]["image_sm"],
                "demo_url": match["demoURLs"][0]
            }
            self.matches[match_id] = match_data
            pre_existing = self.db.insert_match(match_data)
        else:
            stats = self.stats_processor(match_id)
            match_data = {
                "id": match_id,
                "hub": match["entity"]["name"],
                "map_guid": match["voting"]["map"]["pick"][0],
                "map_name": map_name,
                "class_name": [map_object for map_object in match["voting"]["map"]["entities"] if map_object["guid"] == map_guid][0]["class_name"].lower(),
                "room_link": "https://www.faceit.com/en/cs2/room/" + match_id,
                "stats": stats,
                "match_time": match["startedAt"],
                "image": [map_object for map_object in match["voting"]["map"]["entities"] if map_object["guid"] == map_guid][0]["image_sm"],
                "demo_url": "No URL"
            }
            self.matches[match_id] = match_data
            pre_existing = self.db.insert_match(match_data)
            print("no demo url")
        return pre_existing

    def stats_processor(self, match_id):
        '''function to process game stats ready for db store'''
        response = requests.get(STATS_URL + match_id, timeout=5)
        finished_match_data = json.loads(response.text)

        if len(finished_match_data) > 0 and response.status_code == 200:
            team_1 = finished_match_data[0]["teams"][0]["i5"]
            team_1_score = finished_match_data[0]["teams"][0]["c5"]
            team_2 = finished_match_data[0]["teams"][1]["i5"]
            team_2_score = finished_match_data[0]["teams"][1]["c5"]

            team_1_1st_half = finished_match_data[0]["teams"][0]["i3"]
            team_1_2nd_half = finished_match_data[0]["teams"][0]["i4"]
            team_2_1st_half = finished_match_data[0]["teams"][1]["i3"]
            team_2_2nd_half = finished_match_data[0]["teams"][1]["i4"]

            ct_rounds = int(team_1_1st_half) + int(team_2_2nd_half)
            t_rounds = int(team_1_2nd_half) + int(team_2_1st_half)

            match_stats = {
                "CT_1st": {
                    "name": team_1,
                    "final_score": team_1_score,
                    "1st_half": team_1_1st_half,
                    "2nd_half": team_1_2nd_half,
                },
                "T_1st": {
                    "name": team_2,
                    "final_score": team_2_score,
                    "1st_half": team_2_1st_half,
                    "2nd_half": team_2_2nd_half,
                },
                "t_rounds": str(t_rounds),
                "ct_rounds": str(ct_rounds),
            }
        else:
            match_stats = {
                "CT_1st": {
                    "name": "unknown",
                    "final_score": 0,
                    "1st_half": 0,
                    "2nd_half": 0,
                },
                "T_1st": {
                    "name": "unknown",
                    "final_score": 0,
                    "1st_half": 0,
                    "2nd_half": 0,
                },
            }
        return match_stats


#if __name__ == "__main__":
#    mf = MapFetcher("*")
#    mf.backfiller(10, 0)
#    games = mf.db.print_all()
#    print(len(games))
