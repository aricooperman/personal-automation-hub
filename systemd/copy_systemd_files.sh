#!/usr/bin/env bash

DIR=$(cd "$(dirname "$1")"; pwd)

chmod 755 "$DIR"/../run_periodic_jobs.py

sed "s@_PATH_@$DIR/..@g" "$DIR"/automation-hub.service > ~/.config/systemd/user/automation-hub.service

cp "$DIR"/automation-hub.timer ~/.config/systemd/user

systemctl --user enable automation-hub.service
systemctl --user enable automation-hub.timer
systemctl --user start automation-hub.timer