#!/usr/bin/env python3

import sys
import yt
import re
import string
import os
import subprocess as sp

# --- USER CONFIGURATION ---
SUBSONIC_SERVER_URL = os.environ["SUBSONIC_SERVER_URL"]
SUBSONIC_USERNAME = os.environ["SUBSONIC_USERNAME"]
SUBSONIC_PASSWORD = os.environ["SUBSONIC_PASSWORD"]
LOCATION = os.environ["OUTPUT_LOCATION"]

valid_chars = "-_.() %s%s" % (string.ascii_letters, string.digits)
valid_folder_chars = "-_%s%s" % (string.ascii_letters, string.digits)

# Ensure the py-sonic library is installed.
try:
    from libsonic import Connection
except ImportError:
    print("The 'libsonic' library is not installed.")
    print("Please install it by running: pip install py-sonic")
    sys.exit(1)


def download_similar_songs(playlist_title, song: dict):
    count = 0

    folder_title = "".join(c for c in song["title"] if c in valid_folder_chars).lower()
    sp.run(f"mkdir -p {folder_title}", shell=True)

    playlist_fn = f"{playlist_title}.m3u"
    sp.run(f"touch {folder_title}/'{playlist_fn}'", shell=True)

    print(f"creating {playlist_fn}")

    downloaded = set()

    fails_count = 0
    while count < 100:
        at_least_one = False
        songs = yt.get_similar_songs(song["id"])
        for similar in songs:
            if similar["id"] in downloaded:
                continue

            fn = f"{similar['author']} - {similar['title']}.opus"
            fn = "".join(c for c in fn if c in valid_chars)

            try:
                out = sp.check_output(
                    f"yt-dlp -x --no-warnings --embed-metadata https://music.youtube.com/watch?v={similar['id']}",
                    shell=True,
                ).decode("utf8")
            except Exception as e:
                fails_count += 1

                print(f"yt-dlp failed: {e}")
                if fails_count > 10:
                    print("too many fails, exiting...")
                    sys.exit(1)

            m = re.search(r'"(.*\.opus)"', out)
            if not m:
                print(f"could not determine filename from: {out}")

            result_fn = m.group(1).replace("'", "\\'")
            sp.check_output(f"mv '{result_fn}' {folder_title}/'{fn}'", shell=True)
            result_fn = fn

            with open(f"{folder_title}/{playlist_fn}", "a") as f:
                f.write(result_fn)
                f.write("\n")

            print(result_fn)
            count += 1
            at_least_one = True
            downloaded.add(similar["id"])

        if not at_least_one:
            print("Youtube started to return same, exiting...")
            break


def get_radio_playlist(server_url, username, password):
    """
    Connects to a Subsonic server, finds the 'Radio' playlist, and prints its contents.

    Args:
        server_url (str): The URL of your Subsonic server.
        username (str): Your Subsonic username.
        password (str): Your Subsonic password.
    """

    # Initialize the Subsonic client with the provided credentials.
    sub = Connection(server_url, username, password, port=443)

    # Get all playlists from the server.
    playlists = sub.getPlaylists()["playlists"]

    # Search for the playlist named 'Radio'.
    radio_playlist_id = None
    existing_playlists = set()

    for playlist in playlists.get("playlist", []):
        existing_playlists.add(playlist["name"])

        if playlist["name"] == "Radio":
            radio_playlist_id = playlist.get("id")

    if radio_playlist_id:
        details = sub.getPlaylist(radio_playlist_id)["playlist"]
        songs = details.get("entry", [])

        if songs:
            for song in songs:
                playlist_title = "".join(c for c in song["title"] if c in valid_chars)
                if playlist_title in existing_playlists:
                    print(f"Radio based on {song['title']} already exists")
                    continue

                query = f"{song.get('artist')} {song.get('title')}"
                results = yt.search(query)
                if len(results):
                    download_similar_songs(playlist_title, results[0])

        else:
            print("The 'Radio' playlist is empty.")
    else:
        print("The playlist named 'Radio' was not found on your server.")


if __name__ == "__main__":
    get_radio_playlist(SUBSONIC_SERVER_URL, SUBSONIC_USERNAME, SUBSONIC_PASSWORD)
