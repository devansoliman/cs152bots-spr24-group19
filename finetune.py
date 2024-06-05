import json
from google.auth import default
from google.cloud import aiplatform
from google.cloud.aiplatform import TextDataset, TrainingData, TextTrainingDataset
from google.cloud.aiplatform import models
from google.cloud.aiplatform import types
import csv
import random
import os
import re
from collections import defaultdict


credentials, _ = default(scopes=["https://www.googleapis.com/auth/cloud-platform"])

# Project ID and Region (replace with your values)
project_id = "moderation-424102"
region = "us-west1"  # Choose your desired region

# Initialize Vertex AI
vertexai.init(project=project_id, location=region, credentials=credentials)

# Choose a pre-trained text classification model (replace as needed)
model = TextClassificationModel.from_pretrained(
    "distilbert-base-uncased"  # Consider even smaller models if needed
)

# Define training data using TextClassificationDataset
training_data_path = "gs://152_training_data/data/152_finetuning_train.jsonl"
validation_data_path = "gs://152_training_data/data/152_finetuning_val.jsonl"
target_field_name = "label"
class_labels = ["Glorification/Promotion", "Terrorist Account", "Recruitment", "Direct Threat/Incitement", "Financing Terrorism", "None"]

training_data = TrainingData(
    dataset=TextClassificationDataset(
        gcs_source=[training_data_path, validation_data_path]
    ),
    target_field_name=target_field_name,  # Typo fix
    class_labels=class_labels,
)

# Set a budget of $5 (converted to milli-dollars)
budget_milli_dollars = 5 * 1000

# Early stopping (optional, adjust parameters as needed)
early_stopping_steps = 500  # Stop training if validation performance plateaus

tuning_job_settings = TextClassificationTrainingJobSettings(
    model_type=model,
    target_field_name=target_field_name,
    gcs_source_uris=[training_data_path, validation_data_path],
    class_labels=class_labels,
    budget_milli_dollars=budget_milli_dollars,
    early_stopping_steps=early_stopping_steps,  # Add early stopping (optional)
)

# Create Vertex AI Endpoint
endpoint = Endpoint(project=project_id, location=region)

tuning_job = endpoint.create_text_classification_training_job(
    display_name="my-classification-job",
    training_settings=tuning_job_settings,
    tuning_job_location="us-west2",  # Choose a cheaper region
)

try:
  tuning_job.wait()
  print(f"Fine-tuning job completed: {tuning_job.name}")
except Exception as e:
  print(f"An error occurred: {e}")
  # Implement additional error handling as needed
