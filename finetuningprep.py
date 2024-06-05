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

def split_dataset(csv_file, train_file, val_file, test_file, train_size=100, val_size=25):
    """
    Splits a CSV file into training, validation, and test sets, ensuring specific conditions on the splits.

    Args:
        csv_file (str): Path to the input CSV file.
        train_file (str): Path to the output training JSONL file.
        val_file (str): Path to the output validation JSONL file.
        test_file (str): Path to the output test JSONL file.
        train_size (int): Number of training examples.
        val_size (int): Number of validation examples.
    """
    csv_file = remove_null_bytes(csv_file)
    
    data = defaultdict(list)
    categories = ["Glorification/Promotion", "Terrorist Account", "Recruitment", "Direct Threat/Incitement", "Financing Terrorism", "None"]

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

    # Read data from CSV
    with open(csv_file, 'r', encoding="utf-8", errors='replace') as f:
        reader = csv.reader(f, skipinitialspace=True)
        rows = list(reader)
        # Separate the first 75 rows for the test set
        first_75_rows = rows[:75]
        remaining_rows = rows[75:]

        for row in remaining_rows:
            row = [item.strip() for item in row if item.strip()]
            if len(row) != 2:
                print(f"Skipping row: {row}")
                continue
            message, classification = row
            data[classification].append(message)

    # Process the first 75 rows and add them to the test set
    test_data = [(row[0], row[1]) for row in first_75_rows if len(row) == 2 and row[1] in categories]

    # Count the first 75 rows
    first_75_counts = defaultdict(int)
    for message, category in test_data:
        first_75_counts[category] += 1

    print("\nFirst 75 rows category counts:")
    for category, count in first_75_counts.items():
        print(f"{category}: {count}")

    # Calculate proportions for training and validation sets
    total_data_count = sum(len(messages) for messages in data.values())
    train_data = []
    val_data = []
    test_data_full = []

    train_counts = defaultdict(int)
    val_counts = defaultdict(int)
    test_counts = defaultdict(int, first_75_counts)  # Initialize with first 75 rows count

    for category, messages in data.items():
        random.shuffle(messages)
        category_total = len(messages)
        
        train_count = round(train_size * (category_total / total_data_count))
        val_count = round(val_size * (category_total / total_data_count))

        train_data.extend([(message, category) for message in messages[:train_count]])
        val_data.extend([(message, category) for message in messages[train_count:train_count + val_count]])
        test_data_full.extend([(message, category) for message in messages[train_count + val_count:]])

        train_counts[category] += train_count
        val_counts[category] += val_count
        test_counts[category] += category_total - (train_count + val_count)

    # Add first 75 rows to the test data
    test_data_full.extend(test_data)

    # Shuffle the training, validation, and test data
    random.shuffle(train_data)
    random.shuffle(val_data)
    random.shuffle(test_data_full)

    # Convert to JSONL format
    def convert_to_jsonl(data, output_file):
        with open(output_file, 'w', encoding='utf-8') as f:
            count = 0
            for message, category in data:
                input_text = f"You are a content moderator for a social media platform. You are evaluating the following message posted on your platform:\n{message}\n\nUsing the following policy guidelines, evaluate whether the message violates the policies outlined. Choose the best answer between Glorification/Promotion, Terrorist Account, Recruitment, Direct Threat/Incitement, Financing Terrorism, and None for which category the message belongs to. Evaluate based off of our policy, and output the exact category it belongs to. Don't output anything else. Here is the policy:\n{policy}"
                output_text = category.strip()
                item = {
                    "input_text": input_text.strip(),
                    "output_text": output_text.strip()
                }
                json.dump(item, f, ensure_ascii=False)
                f.write('\n')
                count += 1
            print(f"Total entries written to {output_file}: {count}")

    # Convert to JSONL files
    convert_to_jsonl(train_data, train_file)
    convert_to_jsonl(val_data, val_file)
    convert_to_jsonl(test_data_full, test_file)

    print(f"Converted data from {csv_file} to JSONL format in {train_file} (training set), {val_file} (validation set), and {test_file} (test set)")

    # Print counts for each category
    print("\nTraining set category counts:")
    for category, count in train_counts.items():
        print(f"{category}: {count}")

    print("\nValidation set category counts:")
    for category, count in val_counts.items():
        print(f"{category}: {count}")

    print("\nTest set category counts:")
    for category, count in test_counts.items():
        print(f"{category}: {count}")

if __name__ == "__main__":
    # Replace these paths with your actual file paths
    csv_file = r"C:\Users\parke\Downloads\Copy of Group 19 Training Dataset - Sheet1.csv"
    train_file = "152_finetuning_train.jsonl"
    val_file = "152_finetuning_val.jsonl"
    test_file = "152_finetuning_test.jsonl"
    split_dataset(csv_file, train_file, val_file, test_file)
