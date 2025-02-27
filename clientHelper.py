import json
import os

def load_client_config(client_name):
    """
    Load client details from a JSON file with the client's name.
    """
    config_path = os.path.abspath(os.path.join(os.path.dirname(__file__), f"clientDetails/{client_name}.json"))

    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path, "r") as config_file:
        return json.load(config_file)
