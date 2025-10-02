Navidrome (Subsonic) radio (based on Youtube)
---------------------------------------------

Idea - add a song to Radio playlist. In real time scan songs from it and for each song
create a radio playlist (playlist takes the name of the original song) from
Youtube recommendations.

The created playlist will appear in Navidrome and can be played like
a radio (while downloading) from any client.

NOTE: the output location should be in Navidrome tree. Only then it can see
m3u files created by this utility.

Getting started (docker based)
============================

First, create `radio.env` file with following variables:

    SUBSONIC_SERVER_URL="https://music.example.com"
    SUBSONIC_USERNAME="<username>"
    SUBSONIC_PASSWORD="<password>"

Optional variables (with defaults):

* `OUTPUT_LOCATION` = "/music" - where to put the downloaded playlist
* `OUTPUT_COUNT` = 50 - how many similar songs to download
* `OUTPUT_UID` = 1000 - the owner for files
* `OUTPUT_GID` = 1000
* `SUBSONIC_PLAYLIST` = Radio - the playlist with desired radio songs.

Create a `compose.yaml` file:

    services:
      radio:
        image: ghcr.io/ildus/subsonic_radio:main
        restart: unless-stopped
        env_file: radio.env
        volumes:
          - <navidrome music folder>:/music


Now create a playlist in Navidrome with name like in SUBSONIC_PLAYLIST and
add a song to it.

Start the container:

    docker compose up -d

Check the logs:

    docker compose logs
