"""main module for the new bot"""

import sys
import os
import logging
import logging.handlers
import json
import time
from datetime import datetime
import requests

from apscheduler.schedulers.background import BackgroundScheduler
import discord

from discord.ext import commands, tasks

import threading
import asyncio

import webhook_listener
import argparse
import config
import mapcore_functions as mapcorefunctions

import FaceitClasses
from map_fetcher import map_fetcher


class mapcore_bot:

    def __init__(self):

        self.logger = self.build_logger()
        self.port = self.build_parser()

        self.webhooks = webhook_listener.Listener(
            port=self.port, handlers={"POST": self.parse_request}
        )
        self.ongoing_games = {}
        self.completed_games = {}
        self.cancelled_games = {}
        self.games_for_demo = {}
        self.finishing_games = {}
        self.games_with_demo = {}
        self.sched = BackgroundScheduler()
        self.sched.add_job(self.match_tester, "interval", seconds=60)
        self.life = True
        self.map_fetcher = map_fetcher("*", self.logger)

    def start(self):
        """function to start the sub processesS"""
        self.webhooks.start()
        self.sched.start()

    def match_tester(self):
        #print("match_tester")
        #print(self.ongoing_games)
        try:
            for game in self.ongoing_games.values():
                if not (game.finished):
                    game.update_score()
                    score = game.score.get_match_score_string()
                    self.logger.debug(score)

        except Exception as e:
            error_string = f"Error in match_tester, {e}"
            self.logger.error(error_string, exc_info=True)

    def build_logger(self):
        """function to build logger"""
        rootLogger = logging.getLogger()
        rootLogger.setLevel(logging.ERROR)

        logger = logging.getLogger("webhooks")

        console = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            "%(asctime)s :: %(levelname)8s :: %(module)s(%(lineno)d) :: %(message)s",
            datefmt="%Y-%m-%d %I:%M:%S %p",
        )
        console.setFormatter(formatter)
        logger.addHandler(console)

        logPath = os.path.join(os.path.dirname(os.path.realpath(__file__)), "logs")
        if not os.path.exists(logPath):
            os.makedirs(logPath)

        file = logging.handlers.TimedRotatingFileHandler(
            os.path.join(logPath, "webhooks.log"),
            when="midnight",
            interval=1,
            backupCount=7,
        )
        file.setFormatter(formatter)
        logger.addHandler(file)
        logger.debug("Logging started!")

        return logger

    def build_parser(self):
        parser = argparse.ArgumentParser(
            prog="Webhook Listener", description="Start the webhook listener."
        )
        parser.add_argument(
            "--verbose",
            "-v",
            action="store_true",
            dest="verbose",
            help="Enable debug logging.",
        )
        parser.add_argument(
            "--port",
            "-p",
            type=int,
            nargs=1,
            dest="port",
            help="Port for the web server to listen on (default: 8090).",
        )

        
        args = parser.parse_args()
        port = args.port[0] if args.port and args.port[0] >= 0 else 8090
        #print(vars(args))
        self.args = args

        return port

    def match_configure(self, hook_payload):
        #print(self.ongoing_games)
        try:

            debug_message = "made it to match_configure for" + hook_payload["id"]
            self.logger.debug(debug_message)
            match_id = hook_payload["id"]

            match_data = self.match_data_call(match_id)
                
            if match_data[0]:
                match_file = match_id + "/match_status_configuring_match.JSON"
                self.save_file(match_id, match_file, json.dumps(match_data[1]))

                new_match = FaceitClasses.FaceitMatch(
                    match_data[1], "In Warm Up", self.logger
                )
                self.ongoing_games[match_id] = new_match

        except Exception as e:
            error_string = f"Error in match_configure, {e}"
            self.logger.error(error_string, exc_info=True)

    def match_finished(self, hook_payload):
        try:

            debug_message = "made it to match_finished for" + hook_payload["id"]
            self.logger.debug(debug_message)

            match_id = hook_payload["id"]
            if match_id in self.ongoing_games:
                

                closed_match = self.ongoing_games[match_id].finish_match()

                if closed_match:
                    self.ongoing_games[match_id].status = "Finished match"
                    self.ongoing_games[match_id].finished = True
                else:
                    time.sleep(10)
                    self.match_finished(hook_payload)

            else:
                
                previously_saved = self.map_fetcher.check_in_db(match_id)
                if previously_saved:
                    error_string = f"match {match_id} just tried to make itself again in match_finished"
                    self.logger.error(error_string)
                else:
                    self.match_configure(hook_payload)
                    self.ongoing_games[match_id].game_data.map_name = self.ongoing_games[match_id].game_data.map_name
                    self.match_finished(hook_payload)

        except Exception as e:
            error_string = f"Error in match_finished, {e}"
            self.logger.error(error_string, exc_info=True)

        # need to make sure score is complete.

    def match_ready(self, hook_payload):
        debug_message = "made it to match_ready for" + hook_payload["id"]
        self.logger.debug(debug_message)

        match_id = hook_payload["id"]
        if match_id in self.ongoing_games:
            self.ongoing_games[match_id].status = "Configuring"
        else:
            self.match_configure(hook_payload)
            self.match_ready(hook_payload)

    def match_cancelled(self, hook_payload):
        try:

            match_id = hook_payload["id"]
            if "reason" in hook_payload.keys():
                reason = hook_payload["reason"]
            else:
                reason = "Manual"
            debug_message = f"made it to match_cancelled for {match_id} due to {reason}"
            self.logger.debug(debug_message)
            #print(self.ongoing_games.keys())
            if match_id in self.ongoing_games:
                self.ongoing_games[match_id].status = "Cancelled - " + reason
                self.ongoing_games[match_id].cancelled = True
                self.ongoing_games[match_id].cancelled_text = "Cancelled - " + reason +":"

                #self.cancelled_games[match_id] = self.ongoing_games[match_id]
                #self.ongoing_games.pop(match_id)
        except Exception as e:
            error_string = f"Error in match_cancelled, {e}"
            self.logger.error(error_string, exc_info=True)

    def demo_ready(self, hook_payload):
        match_id = hook_payload["id"]

        if match_id in self.ongoing_games:
            processing_game = self.ongoing_games[match_id]
            try:
                if processing_game.demo_needed:
                    self.ongoing_games[match_id].demo_needed = False
                    map_name = processing_game.game_data.map_name

                    #if not os.path.exists(f"{config.STORAGE_LOCATION}{map_name}"):
                    #    os.makedirs(f"{config.STORAGE_LOCATION}{map_name}")
                    #print(hook_payload)
                    if "demo_url" in hook_payload.keys():                    
                        mapcorefunctions.demo_download(hook_payload["demo_url"], match_id, map_name, self.logger)
                        processing_game.demoed = True
                        stored_in_db = self.map_fetcher.finished_match_processor(match_id)
                        self.ongoing_games[match_id] = processing_game
            except Exception as e:
                error_string = f"Error in demo_ready, {e}"
                self.logger.error(error_string, exc_info=True)
        else:
            previously_saved = self.map_fetcher.check_in_db(match_id)
            if previously_saved:
                error_string = f"match {match_id} just tried to make itself again in demo ready"
                self.logger.error(error_string)
            else:
                self.match_finished(hook_payload)
                self.ongoing_games[match_id].game_data.map_name = self.ongoing_games[match_id].game_data.map_name
                self.demo_ready(hook_payload)

    def match_data_call(self, match_id):

        try:
            response = requests.get(config.MATCH_URL + match_id, timeout=5)
            if len(response.text) > 0:
                data = json.loads(response.text)
                if "voting" in data["payload"]:

                    return (True, data)
                else:
                    time.sleep(30)
                    self.match_data_call(match_id)

        except Exception as e:
            error_string = f'"Error in match_data_call", {e}'
            self.logger.error(error_string)
            return (False, "Failed")

    def process_body(self, request):

        body_raw = (
            request.body.read(int(request.headers["Content-Length"]))
            if int(request.headers.get("Content-Length", 0)) > 0
            else ""
        )
        if int(request.headers.get("Content-Length", 0)) > 0:
            body = json.loads(body_raw.decode("utf-8"))
        else:
            body = "{}"

        return body

    def save_file(self, match_id, file_name, data):
        cloud_path = f'match_data/{match_id}'
        if not os.path.exists(cloud_path):
            os.makedirs(cloud_path)
        full_file_name = 'match_data/'+file_name
        try:
            with open(full_file_name, "w") as myFile:
                myFile.write(data)

        except Exception as e:
            self.logger.error(f"{full_file_name} has an issue saving file, {e}")
            #print(file_name)

    def process_hook_info(self, request, body, *args, **kwargs):

        request_info = (
                "Received request:\n"
                + "Method: {}\n".format(request.method)
                + "Headers: {}\n".format(request.headers)
                + "Args (url path): {}\n".format(args)
                + "Keyword Args (url parameters): {}\n".format(kwargs)
                + "Body:{}\n".format(json.dumps(body))
            )

        event = body["event"]
        match_id = body["payload"]["id"]
        file_name = match_id + "/" + event + "_hook.JSON"
        self.save_file(match_id, file_name, request_info)


    def parse_request(self, request, *args, **kwargs):
        self.logger.debug("made it to parser")

        if "USER-AGENT" in request.headers and "WIBBLE" in request.headers:

            user_agent = request.headers["USER-AGENT"]
            wibble = request.headers["WIBBLE"]
            check_string = f"user_agent {user_agent} {user_agent==config.USER_AGENT}, wibble {wibble} {wibble==config.WIBBLE}"
            self.logger.debug(check_string)
            if user_agent==config.USER_AGENT and wibble==config.WIBBLE:

            
                body = self.process_body(request)

                
                self.process_hook_info(request, body, *args, **kwargs)

                self.logger.debug("made it to match data")

                functionDictionary = {
                    "match_status_configuring": self.match_configure,
                    "match_status_ready": self.match_ready,
                    "match_status_finished": self.match_finished,
                    "match_status_cancelled": self.match_cancelled,
                    "match_demo_ready": self.demo_ready,
                }

                if body["event"] in functionDictionary.keys():
                    self.logger.debug(f'{body["event"]} for {body["payload"]["id"]} match')
                    functionDictionary[body["event"]](body["payload"])
                else:
                    debug_msg = body["event"] + " not handled"
                    self.logger.debug(debug_msg)
            else:
                debug_msg = "failed user agent and wibble check"
                self.logger.debug(debug_msg)
        else:
            debug_msg = "no user agent or wibble"
            self.logger.debug(debug_msg)

        return

if __name__ == "__main__":
    #print("hello world")

    mapcore_bot = mapcore_bot()

    while mapcore_bot.life:
        #print("hello world")
        mapcore_bot.logger.debug("Still alive...")
        time.sleep(300)
