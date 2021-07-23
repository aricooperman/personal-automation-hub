# Personal Automation Hub

Python based set of functions and cron jobs to integrate and move different tasks from different utilities:

* IMAP Servers to ingest tasks (tested with GMail)
* SMTP Servers to send to email based service endpoints
* [Joplin](https://joplin.cozic.net/) API for storing tasks
* [Todoist](https://todoist.com/) API for actionable tasks

## Joplin Integration
This project heavily utilized [joplin-mail-gateway](https://github.com/manolitto/joplin-mail-gateway) and much thanks to 
[Manfred Geiler's](https://github.com/manolitto) for his work on it. The bash scripts were converted to python scripts, 
instead of POP I use IMAP, and I had trouble using Joplin CLI with some notes size and/or formatting trying to pass on 
command line so I choose to use the Joplin API instead. Otherwise the Joplin piece, including OCR and PDF thumbnailing 
is taken from joplin-mail-gateway

## Prerequisites

1. [**Joplin**](https://joplin.cozic.net/) terminal or desktop application with API server turned on
2. [**pdftoppm**](https://poppler.freedesktop.org/) and [**pdftotext**](https://poppler.freedesktop.org/) for PDF thumbnails and text extraction
3. [**tesseract**](https://github.com/tesseract-ocr/tesseract) for image OCR
4. [**python 3**](https://www.python.org/) for all the python scripts (tested with 3.9)
5. **python Libraries** - PyYAML & requests - install using included requirements.txt file

## Install

1. Clone from github

        git clone https://github.com/aricooperman/personal-automation-hub.git
   
2. Create the configuration file
        
        cp config-example.yml config.yml
        
3. Update configuration values

4. Install dependencies into project space

         pip install -r requirements.txt --prefix vendor

5. Run main script
        
        ./run_periodic_jobs.py
        
6. Add scheduled job via cron or systemctl timers

        crontab -e

    Add the following line (for example to run every 15 minutes):

        */15 * * * * PYTHONPATH=<path to project>/vendor/lib/python3.9/site-packages python <path to project>/run_periodic_jobs.py >> <path to log file> 2>&1  

   *OR*

   Go to systemd directory and run 

         ./copy_systemd_files.sh

## Running from a docker container

To setup the docker container :

1. prepare the mail-gateway by editing the `config.sh` file as described above

2. edit the `joplin-config.json` file with your Joplin sync settings. Template files are availables. Simple remove the `.template` extension

3. build the container by running

        docker build . -t joplin_gateway

4. run the container

        docker run -d joplin_gateway
