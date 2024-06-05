import csv
import json
import random
from collections import defaultdict

def remove_null_bytes(file_path):
    """
    Removes null bytes from a file.
    
    Args:
        file_path (str): Path to the input file.
        
    Returns:
        str: Path to the cleaned file.
    """
    cleaned_file_path = file_path + ".cleaned"
    with open(file_path, 'rb') as f_in, open(cleaned_file_path, 'wb') as f_out:
        for line in f_in:
            f_out.write(line.replace(b'\0', b''))
    return cleaned_file_path

def process_first_75(csv_file, output_file):
    """
    Processes the first 75 entries from a CSV file and writes them to a JSONL file.
    
    Args:
        csv_file (str): Path to the input CSV file.
        output_file (str): Path to the output JSONL file.
    """
    csv_file = remove_null_bytes(csv_file)
    policy = """Overview
    Our platform prohibits content that supports or represents violent extremist organizations and entities, including those designated by the U.S. government as Foreign Terrorist Organizations. Prohibited content may fall into the following categories: 
    1. Glorification and/or Promotion of Terrorism or a Terrorist Entity
    2. Financing Terrorist Activity
    3. Terrorist Recruitment
    4. Direct Threats/Incitement to Violence

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
    
    categories = ["Glorification/Promotion", "Terrorist Account", "Recruitment", "Direct Threat/Incitement", "Financing Terrorism", "None"]
    first_75_data = []

    with open(csv_file, 'r', encoding="utf-8", errors='replace') as f:
        reader = csv.reader(f, skipinitialspace=True)
        rows = list(reader)
        first_75_rows = rows[:75]

        for row in first_75_rows:
            row = [item.strip() for item in row if item.strip()]
            if len(row) != 2:
                print(f"Skipping row: {row}")
                continue
            message, classification = row
            if classification in categories:
                input_text = f"Classify the following text into one of the following classes: {', '.join(categories[:-1])}, and {categories[-1]}. Text: {message}"
                output_text = classification.strip()
                item = {
                    "input_text": input_text.strip(),
                    "output_text": output_text.strip()
                }
                first_75_data.append(item)

    # Write first 75 entries to JSONL file
    with open(output_file, 'w', encoding='utf-8') as f_out:
        for item in first_75_data:
            json.dump(item, f_out, ensure_ascii=False)
            f_out.write('\n')

    print(f"Processed first 75 entries and saved to {output_file}")

if __name__ == "__main__":
    # Replace these paths with your actual file paths
    csv_file = r"C:\Users\parke\Downloads\Copy of Group 19 Training Dataset - Sheet1.csv"
    output_file = "first_75.jsonl"
    process_first_75(csv_file, output_file)
