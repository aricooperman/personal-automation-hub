import os
import yaml

config_dir = os.path.dirname(__file__)
config_file_path = os.path.join(config_dir, 'config.yml')

with open(config_file_path, "r") as yml_file:
    configs = yaml.load(yml_file, Loader=yaml.FullLoader)
    mail_configs = configs['mail']
    joplin_configs = configs['joplin']
    # file_configs = configs['file']
    todoist_configs = configs['todoist']
    kindle_configs = configs['kindle']
    trello_configs = configs['trello']
