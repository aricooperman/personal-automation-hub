#!/usr/bin/env bash


cp  automation-hub.service automation-hub.timer ~/.config/systemd/user
systemctl --user enable automation-hub.service
