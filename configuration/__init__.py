import yaml

try:
    with open("config.yaml", 'r') as config:
        data = yaml.safe_load(config)
        config = data
except FileNotFoundError:
    raise FileNotFoundError("\nPlease create a 'config.yaml' file and put the credentials needed for the bot in it.\nRefer configuration/example_config.yaml for a template")
