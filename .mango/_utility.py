'''
_utility.py
----------------
This file contains _utility functions for the canvas homework management system.
'''

import os

def get_env_variables():
    # Append .env to the list of environment variable files to load
    dir_of_script = os.path.dirname(os.path.abspath(__file__))
    env_files = ['.env', os.path.join(dir_of_script, '.env')]
    for env_file in env_files:
        try:
            with open(env_file) as f:
                for line in f:
                    if line.strip() and not line.startswith('#'):
                        key, value = line.strip().split('=', 1)
                        os.environ[key] = value
        except FileNotFoundError:
            pass
    # Return the loaded environment variables as a dictionary
    return {key: os.environ[key] for key in os.environ}

def get_oc_api_key():
    env_vars = get_env_variables()
    if env_vars.get('OC_API_KEY'):
        return env_vars['OC_API_KEY']
    raise ValueError("OC_API_KEY not found in environment variables. Please set it in a .env file or as an environment variable.")
