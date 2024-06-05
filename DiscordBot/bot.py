# bot.py
import discord
from discord.ext import commands
import os
import json
import logging
import re
import requests
from report import Report
import pdb
import traceback
import asyncio
import vertexai
from vertexai.generative_models import GenerativeModel
from googleapiclient import discovery
from dotenv import load_dotenv


# Set up logging to the console
logger = logging.getLogger('discord')
logger.setLevel(logging.DEBUG)
handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
logger.addHandler(handler)

# There should be a file called 'tokens.json' inside the same folder as this file
token_path = 'tokens.json'
if not os.path.isfile(token_path):
    raise Exception(f"{token_path} not found!")
with open(token_path) as f:
    # If you get an error here, it means your token is formatted incorrectly. Did you put it in quotes?
    tokens = json.load(f)
    discord_token = tokens['discord']


class ModBot(discord.Client):
    def __init__(self): 
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix='.', intents=intents)
        self.group_num = None
        self.mod_channels = {} # Map from guild to the mod channel id for that guild
        self.reports = {} # Map from user IDs to the state of their report
        self.require_approval = 1
        self.verify = 0
        self.waiting_mod = 0

    async def on_ready(self):
        print(f'{self.user.name} has connected to Discord! It is these guilds:')
        for guild in self.guilds:
            print(f' - {guild.name}')
        print('Press Ctrl-C to quit.')

        # Parse the group number out of the bot's name
        match = re.search('[gG]roup (\d+) [bB]ot', self.user.name)
        if match:
            self.group_num = match.group(1)
        else:
            raise Exception("Group number not found in bot's name. Name format should be \"Group # Bot\".")

        # Find the mod channel in each guild that this bot should report to
        for guild in self.guilds:
            for channel in guild.text_channels:
                if channel.name == f'group-{self.group_num}-mod':
                    self.mod_channels[guild.id] = channel
        

    async def on_message(self, message):
        '''
        This function is called whenever a message is sent in a channel that the bot can see (including DMs). 
        Currently the bot is configured to only handle messages that are sent over DMs or in your group's "group-#" channel. 
        '''
        # Ignore messages from the bot 
        if message.author.id == self.user.id:
            return

        # Check if this message was sent in a server ("guild") or if it's a DM
        if message.guild:
            await self.handle_channel_message(message)
        else:
            await self.handle_dm(message)           

    async def handle_dm(self, message):
        try:
            # Handle a help message
            if message.content == Report.HELP_KEYWORD:
                reply =  "Use the `report` command to begin the reporting process.\n"
                reply += "Use the `cancel` command to cancel the report process.\n"
                await message.channel.send(reply)
                return

            author_id = message.author.id
            responses = []

            # Only respond to messages if they're part of a reporting flow
            if author_id not in self.reports and not message.content.startswith(Report.START_KEYWORD):
                return

            # If we don't currently have an active report for this user, add one
            if author_id not in self.reports:
                self.reports[author_id] = Report(self)

            # Let the report class handle this message; forward all the messages it returns to uss
            responses = await self.reports[author_id].handle_message(message)
            for r in responses:
                await message.channel.send(r)


            ### CURRENTLY TESTING - FEATURE FOR LOGGING REPORTS
            try: 
                mod_channel = None
                for guild in self.guilds:
                    for channel in guild.text_channels:
                        if channel.name == f'group-{self.group_num}-mod':
                            mod_channel = channel

            # If the report is ready to be moderated, send log to moderator in mod-channel
                if self.reports[author_id].report_moderate_ready():
                    ## extract content for logs message
                    report_type, reported_content = self.reports[author_id].get_report_info()
                    reported_guild = reported_content[0]
                    reported_channel = reported_content[1]
                    reported_message = reported_content[2]

                    old_approval_mode = self.require_approval

                    if report_type == "glorification or promotion":
                        self.require_approval = 0
                    

                    ## send logs message
                    reply = "MESSAGE_TO_MODERATOR_LOGS:\n"
                    reply += "Report received violation of type: " + report_type + "\n"
                    reply += "The reported message sent was in this guild: " + str(reported_guild) + "\n"
                    reply += "Sent in channel: " + str(reported_channel) + "\n"
                    reply += "Reported message:" + "```" + reported_message.author.name + ": " + reported_message.content + "```" + "\n-\n-\n"
                    await asyncio.sleep(1)
                    await mod_channel.send(reply)
                    
                    message_to_user = self.reports[author_id].get_moderation_message_to_user()
                    await asyncio.sleep(1)
                    await mod_channel.send(message_to_user)
                    platform_action = self.reports[author_id].get_platform_action()
                    await asyncio.sleep(1)
                    await mod_channel.send(platform_action)

                    await self.seek_verification()        

                    self.require_approval = old_approval_mode

                    self.reports[author_id].end_report()

            except Exception as e:
                # Get the stack trace as a string
                stack_trace = traceback.format_exc()
                
                # Construct the error message with detailed information
                error_message = (
                    "Oops! Something went wrong. Here's the error message and additional details:\n\n"
                    f"Error Type: {type(e).__name__}\n"
                    f"Error Details: {str(e)}\n\n"
                    "Stack Trace:\n"
                    f"{stack_trace}"
                )
                
                # Send the detailed error message to the Discord channel
                await message.channel.send(error_message)
                return

            # If the report is complete or cancelled, remove it from our map
            if self.reports[author_id].report_complete():
                self.reports.pop(author_id)

                
        except Exception as e:
                # Get the stack trace as a string
                stack_trace = traceback.format_exc()
                
                # Construct the error message with detailed information
                error_message = (
                    "Oops! Something went wrong. Here's the error message and additional details:\n\n"
                    f"Error Type: {type(e).__name__}\n"
                    f"Error Details: {str(e)}\n\n"
                    "Stack Trace:\n"
                    f"{stack_trace}"
                )
                
                # Send the detailed error message to the Discord channel
                await message.channel.send(error_message)
                return

    async def handle_channel_message(self, message):
        try:
            mod_channel = self.mod_channels[message.guild.id]
    
            if message.channel.name == f'group-{self.group_num}-mod':

                ### keywords

                if message.content == 'Require moderator':
                    self.require_approval = 1
                    self.waiting_mod = 0
                    reply = "MESSAGE_TO_MODERATOR_LOGS\n"
                    reply += "Moderator manual review now required." + "\n-\n-\n"
                    await asyncio.sleep(1)
                    await mod_channel.send(reply)
                    
                if message.content == "Automatic system review":
                    self.require_approval = 0
                    reply = "MESSAGE_TO_MODERATOR_LOGS\n"
                    reply += "Moderator manual review is now not required." + "\n-\n-\n"
                    await asyncio.sleep(1)
                    await mod_channel.send(reply)

                if self.waiting_mod == 1:
                    if message.content == 'yes':
                        reply = "MESSAGE_TO_MODERATOR_LOGS\n"
                        reply += "Moderator has determined the previous report is indeed in violation of community guidelines. The previous pending actions will be taken." + "\n-\n-\n"
                        self.waiting_mod = 0
                    elif message.content == 'no':
                        reply = "MESSAGE_TO_MODERATOR_LOGS\n"
                        reply += "Moderator has determined the previous report was not in violation of community guidelines. No further action is needed." + "\n-\n-\n"
                        self.waiting_mod = 0
                    else:
                        reply = "MESSAGE_TO_MODERATOR_LOGS\n"
                        reply += "That is not a valid choice; please select 'yes' or 'no'" + "\n-\n-\n"
                    await asyncio.sleep(1)
                    await mod_channel.send(reply)
                    

        except Exception as e:
                # Get the stack trace as a string
                stack_trace = traceback.format_exc()
                
                # Construct the error message with detailed information
                error_message = (
                    "Oops! Something went wrong. Here's the error message and additional details:\n\n"
                    f"Error Type: {type(e).__name__}\n"
                    f"Error Details: {str(e)}\n\n"
                    "Stack Trace:\n"
                    f"{stack_trace}"
                )
                
                # Send the detailed error message to the Discord channel
                await message.channel.send(error_message)
                return


        if not message.channel.name == f'group-{self.group_num}':
            return

        # Forward the message to the mod channel
        ## gemini prompting
        await self.gemini_review(message)
        await self.persepctive_review(message)
        
        ##await mod_channel.send(f'Forwarded message:\n{message.author.name}: "{message.content}"')
        ##scores = self.eval_text(message.content)
        ##await mod_channel.send(self.code_format(scores))

    async def persepctive_review(self, message):
        load_dotenv()
        mod_channel = self.mod_channels[message.guild.id]

        perspective_API_key = os.getenv("perspective_API_key")
        service = discovery.build(
            "commentanalyzer",
            "v1alpha1",
            developerKey=perspective_API_key,
            discoveryServiceUrl="https://commentanalyzer.googleapis.com/$discovery/rest?version=v1alpha1",
            static_discovery=False,
        )
        analyze_request = {
            'comment': {'text': message.content, 'type': 'PLAIN_TEXT'},
            'languages': ["en"],
            "requestedAttributes": {
                "TOXICITY": {},
                "SEVERE_TOXICITY": {},
                "INSULT": {},
                "PROFANITY": {},
                "IDENTITY_ATTACK": {},
                "THREAT": {},
            },
        }
        try:
            # Execute the analyze request
            response = service.comments().analyze(body=analyze_request).execute()
            scores = response['attributeScores']
        except Exception as e:
            # Get the stack trace as a string
            stack_trace = traceback.format_exc()
            
            # Construct the error message with detailed information
            error_message = (
                "Oops! Something went wrong. Here's the error message and additional details:\n\n"
                f"Error Type: {type(e).__name__}\n"
                f"Error Details: {str(e)}\n\n"
                "Stack Trace:\n"
                f"{stack_trace}"
            )
            
            # Send the detailed error message to the Discord channel
            await message.channel.send(error_message)
            return
        
        low_thresholds = {
            "toxicity": 0.7,
            "severe_toxicity": 0.5,
            "insult": 0.7,
            "profanity": 0.6,
            "identity_attack": 0.5,
            "threat": 0.5,
        }

        high_thresholds = {
            "toxicity": 0.95,
            "severe_toxicity": 0.75,
            "insult": 0.95,
            "profanity": 0.95,
            "identity_attack": 0.75,
            "threat": 0.75,
        }

        logs_reply = "MESSAGE_TO_MODERATOR_LOGS:\n"
        logs_reply += "Results from Google Perspective review of the following message: " + message.content + "\n"
        user_reply = "MESSAGE_TO_USER (" + message.author.name + "):\n"
        user_reply += "You posted the following: " + message.content + "\n"
        user_flag = 0
        server_reply = "\nSERVER_ACTION\n"
        server_reply += "The following post has been deleted from the platform after automatic detection via Google Perspective of a policy violation. \n"
        server_reply += "```" + message.author.name + ": " + message.content + "```"

        if scores.get("TOXICITY", {}).get("summaryScore", {}).get("value", 0) > high_thresholds["toxicity"]:
            logs_reply += "This message violates our policy for toxicity, and it has been deleted from the platform." + "\n-\n-\n"
            user_flag = 1
            user_reply += "The above post has violated our terms and conditions for toxicity and has been deleted. If you think we made a mistake, send a message to fakeaddress@fakeplatform.com to appeal." + "\n-\n-\n"
        elif scores.get("SEVERE_TOXICITY", {}).get("summaryScore", {}).get("value", 0) > high_thresholds["severe_toxicity"]:
            logs_reply += "This message violates our policy for severe toxicity, and it has been deleted from the platform." + "\n-\n-\n"
            user_flag = 1
            user_reply += "The above post has violated our terms and conditions for toxicity and has been deleted. If you think we made a mistake, send a message to fakeaddress@fakeplatform.com to appeal." + "\n-\n-\n"
        elif scores.get("INSULT", {}).get("summaryScore", {}).get("value", 0) > high_thresholds["insult"]:
            logs_reply += "This message violates our policy for insults, and it has been deleted from the platform." + "\n-\n-\n"
            user_flag = 1
            user_reply += "The above post has violated our terms and conditions for toxicity and has been deleted. If you think we made a mistake, send a message to fakeaddress@fakeplatform.com to appeal." + "\n-\n-\n"
        elif scores.get("PROFANITY", {}).get("summaryScore", {}).get("value", 0) > high_thresholds["profanity"]:
            logs_reply += "This message violates our policy for profanity, and it has been deleted from the platform." + "\n-\n-\n"
            user_flag = 1
            user_reply += "The above post has violated our terms and conditions for toxicity and has been deleted. If you think we made a mistake, send a message to fakeaddress@fakeplatform.com to appeal." + "\n-\n-\n"
        elif scores.get("IDENTITY_ATTACK", {}).get("summaryScore", {}).get("value", 0) > high_thresholds["identity_attack"]:
            logs_reply += "This message violates our policy for identity attacks, and it has been deleted from the platform." + "\n-\n-\n"
            user_flag = 1
            user_reply += "The above post has violated our terms and conditions for toxicity and has been deleted. If you think we made a mistake, send a message to fakeaddress@fakeplatform.com to appeal." + "\n-\n-\n"
        elif scores.get("THREAT", {}).get("summaryScore", {}).get("value", 0) > high_thresholds["threat"]:
            logs_reply += "This message violates our policy for threats, and it has been deleted from the platform." + "\n-\n-\n"
            user_flag = 1
            user_reply += "The above post has violated our terms and conditions for toxicity and has been deleted. If you think we made a mistake, send a message to fakeaddress@fakeplatform.com to appeal." + "\n-\n-\n"
        elif scores.get("TOXICITY", {}).get("summaryScore", {}).get("value", 0) > low_thresholds["toxicity"]:
            logs_reply += "This message might violate our policy for toxicity; it has been downranked in the algorithm." + "\n-\n-\n"
        elif scores.get("SEVERE_TOXICITY", {}).get("summaryScore", {}).get("value", 0) > low_thresholds["severe_toxicity"]:
            logs_reply += "This message might violate our policy for severe_toxicty; it has been downranked in the algorithm." + "\n-\n-\n"
        elif scores.get("INSULT", {}).get("summaryScore", {}).get("value", 0) > low_thresholds["insult"]:
            logs_reply += "This message might violate our policy for insults; it has been downranked in the algorithm." + "\n-\n-\n"
        elif scores.get("PROFANITY", {}).get("summaryScore", {}).get("value", 0) > low_thresholds["profanity"]:
            logs_reply += "This message might violate our policy for profanity; it has been downranked in the algorithm." + "\n-\n-\n"
        elif scores.get("IDENTITY_ATTACK", {}).get("summaryScore", {}).get("value", 0) > low_thresholds["identity_attack"]:
            logs_reply += "This message might violate our policy for indentity attacks; it has been downranked in the algorithm." + "\n-\n-\n"
        elif scores.get("THREAT", {}).get("summaryScore", {}).get("value", 0) > low_thresholds["threat"]:
            logs_reply += "This message might violate our policy for threats; it has been downranked in the algorithm." + "\n-\n-\n"
        else:
            logs_reply += "This message does not violate our policies for general moderation; no action has been taken" + "\n-\n-\n"

        await mod_channel.send(logs_reply)
        await asyncio.sleep(1)
        if user_flag == 1:
            await mod_channel.send(user_reply)
            await asyncio.sleep(1)
            await mod_channel.send(server_reply)


    async def gemini_review(self, message):
        mod_channel = self.mod_channels[message.guild.id]
        try:
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "service-account.json"

            project_id = "moderation-424102"  ## for parker's gcloud account, please use responsibly <3
            vertexai.init(project=project_id, location="us-central1")
            model = GenerativeModel(model_name="gemini-1.0-pro-002")
            categories = ["glorification/promotion", "terrorist account", "recruitment", "direct threat/incitement", "financing terrorism"]
            policy = """Our platform prohibits content that supports or represents violent extremist organizations and entities, including those designated by the U.S. government as Foreign Terrorist Organizations. Prohibited content may fall into the following categories: Glorification and/or Promotion of Terrorism or a Terrorist Entity, Financing Terrorist Activity, Terrorist Recruitment, Direct Threats/Incitement to Violence, and Accounts Representing Terrorist Entities.

What is a Violation of our Policy?
- Financing Terrorism: Providing material support to a designated terrorist organization is a federal crime in the U.S. (18 USC 2339B) and is strictly prohibited on our platform. Examples may include:
    - Requests for donations to fund terrorist activities or groups.
    - Soliciting funds for weapons, explosives, or other tools of violence.
    - Encouraging others to provide material support for terrorism.
    - Sharing links to GoFundMe pages or crypto trading sites meant to support terrorist organizations.

- Glorification/Promotion of Terrorism: We do not allow any content that glorifies or in any way promotes the actions or ideology of terrorist groups. Examples may include:
    - Celebrating or praising terrorist attacks or organizations.
    - Sharing images/videos that depict violence in a way that seeks to glorify or justify them.
    - Posting or linking to manifestos, speeches, and/or writings of terrorist leaders.
    - Justifying terrorist actions as necessary or heroic.

- Incitement/Direct Threat: We remove content that calls for attacks on the general public or specific individuals. This includes content that promotes violence due to a specific cause. Examples may include:
    - Direct threats of violence towards individuals or groups.
    - Calls to or instructions for violent attacks.
    - Content that incites others to commit acts of terrorism.
    - Instructions on how to carry out violent attacks.

- Terrorist Recruitment: We do not allow content that is meant to recruit individuals to join terrorist organizations. Additionally, we remove content that also sympathizes with terrorism. Examples may include:
    - Posts or messages that explicitly recruit individuals to join terrorist groups.
    - Propaganda that romanticizes membership of a terrorist organization.
    - Announcements or invitations to attend events or training camps organized by terrorist organizations."""
            prompt = f"You are a content moderator for a social media platform. You are evaluating the following message posted on your platform:\n{message.content}\n\nUsing the following policy guidelines, evaluate whether the message violates the policies outlined. Choose the best answer between Glorification/Promotion, Terrorist Account, Recruitment, Direct Threat/Incitement, Financing Terrorism, and None for which category the message belongs to. Evaluate based off of our policy, and output the exact category it belongs to. Don't output anything else. Here is the policy:\n{policy}"
            
            response = model.generate_content(
                prompt
            )


            logs_reply = "MESSAGE_TO_MODERATOR_LOGS:\n"
            logs_reply += "Results from Google Gemini review of the following message: " + message.content + "\n"
            user_reply = "MESSAGE_TO_USER (" + message.author.name + "):\n"
            user_reply += "You posted the following: " + message.content + "\n"
            user_flag = 0
            server_reply = "\nSERVER_ACTION\n"
            server_reply += "The following post has been deleted from the platform after automatic detection via Google Gemini of a violation of our policy on terrorism. \n"
            server_reply += "```" + message.author.name + ": " + message.content + "```" + "\n-\n-\n"

            if response.text.lower() == "none":
                logs_reply += "Gemini classified this message as: likely not a violation" + "\n"
            else:
                logs_reply += "Gemini classified this message as: " + response.text.lower() + "\n"
            


            if response.text.lower() in categories:
                logs_reply += "As such, the message has been deleted from our platform."
                if response.text.lower() != "glorification/promotion":
                    logs_reply += "A report has also been made to law enforcement for the user & corresponding message." + "\n-\n-\n"
                    await mod_channel.send(logs_reply)
                    await asyncio.sleep(2)
                else:
                    logs_reply += " If applicable, the content has been also been uploaded to the GIFCT hash bank if it wasn't already." + "\n-\n-\n"
                    await mod_channel.send(logs_reply)
                    await asyncio.sleep(2)
                await mod_channel.send(server_reply)
                await asyncio.sleep(2)
                user_reply += "This message has been deleted, as it violates our policy for terrorism. Please refer to our terms of service for what is acceptable on our platform." + "\n-\n-\n"
                await mod_channel.send(user_reply)
            else:
                logs_reply += "As such, no action will be taken." "\n-\n-\n"
                await mod_channel.send(logs_reply)

            await asyncio.sleep(5)

        except Exception as e:
                # Get the stack trace as a string
                stack_trace = traceback.format_exc()
                
                # Construct the error message with detailed information
                error_message = (
                    "Oops! Something went wrong. Here's the error message and additional details:\n\n"
                    f"Error Type: {type(e).__name__}\n"
                    f"Error Details: {str(e)}\n\n"
                    "Stack Trace:\n"
                    f"{stack_trace}"
                )
                
                # Send the detailed error message to the Discord channel
                await mod_channel.send(error_message)
                return

    
    def eval_text(self, message):
        ''''
        TODO: Once you know how you want to evaluate messages in your channel, 
        insert your code here! This will primarily be used in Milestone 3. 
        '''
        return message

    
    def code_format(self, text):
        ''''
        TODO: Once you know how you want to show that a message has been 
        evaluated, insert your code here for formatting the string to be 
        shown in the mod channel. 
        '''
        return "Evaluated: '" + text+ "'"
    
    async def seek_verification(self):
        try: 
            mod_channel = None
            for guild in self.guilds:
                for channel in guild.text_channels:
                    if channel.name == f'group-{self.group_num}-mod':
                        mod_channel = channel

            if self.require_approval == 1:
                reply = "MESSAGE_TO_MODERATOR_LOGS\n"
                reply += "The previous message must undergo moderator review. Reply 'yes' if the post is in violation of community guidelines, otherwise 'no'" + "\n-\n-\n"
                await mod_channel.send(reply)
                self.waiting_mod = 1
            else:
                reply = "MESSAGE_TO_MODERATOR_LOGS\n"
                reply += "The previous message does not need moderator review, and the previous pending actions will be taken." + "\n-\n-\n"
                await mod_channel.send(reply)


        except Exception as e:
                # Get the stack trace as a string
                stack_trace = traceback.format_exc()
                
                # Construct the error message with detailed information
                error_message = (
                    "Oops! Something went wrong. Here's the error message and additional details:\n\n"
                    f"Error Type: {type(e).__name__}\n"
                    f"Error Details: {str(e)}\n\n"
                    "Stack Trace:\n"
                    f"{stack_trace}"
                )
                
                # Send the detailed error message to the Discord channel
                await mod_channel.send(error_message)
                return

        


client = ModBot()
client.run(discord_token)