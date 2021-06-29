import sys
import os
import yaml

CURR_WD = os.getcwd()
os.chdir(sys.path[0])

with open("config.yml", "r") as yml_file:
    configs = yaml.load(yml_file, Loader=yaml.FullLoader)
    mail_configs = configs['mail']
    joplin_configs = configs['joplin']
    evernote_configs = configs['evernote']

os.chdir(CURR_WD)
