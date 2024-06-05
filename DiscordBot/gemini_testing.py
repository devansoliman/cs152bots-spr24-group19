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

def evaluate_model_accuracy():
    try:
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "service-account.json"

        project_id = "moderation-424102"
        vertexai.init(project=project_id, location="us-central1")
        model = GenerativeModel(model_name="gemini-1.0-pro-002")
        
        # Prompt template
        prompt_template = """
        You are a content moderator for a social media platform. You are evaluating the following message posted on your platform:
        {input_text}
        
        Using the following policy guidelines, evaluate whether the message violates the policies outlined. Choose the best answer between Glorification/Promotion, Terrorist Account, Recruitment, Direct Threat/Incitement, Financing Terrorism, and None for which category the message belongs to. Evaluate based off of our policy, and output the exact category it belongs to. Don't output anything else. Here is the policy:
        Our platform prohibits content that supports or represents violent extremist organizations and entities, including those designated by the U.S. government as Foreign Terrorist Organizations. Prohibited content may fall into the following categories: Glorification and/or Promotion of Terrorism or a Terrorist Entity, Financing Terrorist Activity, Terrorist Recruitment, Direct Threats/Incitement to Violence, and Accounts Representing Terrorist Entities.
        
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
            - Announcements or invitations to attend events or training camps organized by terrorist organizations.
        """

        # Read the examples from the JSONL file
        examples = []
        with open('examples.jsonl', 'r') as file:
            for line in file:
                examples.append(json.loads(line))
        
        correct_count = 0
        total_examples = len(examples)
        
        # Query the model for each example and compare with expected output
        for example in examples:
            prompt = prompt_template.format(input_text=example['input_text'])
            response = model.generate_content(prompt, temperature=0)
            model_output = response.text.strip()
            
            if model_output.lower() == example['output_text'].strip().lower():
                correct_count += 1
            else:
                print(f"Incorrect response:\nInput: {example['input_text']}\nExpected: {example['output_text']}\nGot: {model_output}\n")

        accuracy = (correct_count / total_examples) * 100
        
        # Print the percentage of correct answers
        print(f"Model accuracy: {accuracy:.2f}%")
        
    except Exception as e:
        print(f"An error occurred: {e}")

# Run the evaluation
evaluate_model_accuracy()