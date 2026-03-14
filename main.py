#!/usr/bin/env python3

import sys
import yt
import re
import os
import json
import subprocess as sp
import time
import signal
import urllib.request

# --- USER CONFIGURATION ---
SUBSONIC_SERVER_URL = os.environ["SUBSONIC_SERVER_URL"]
SUBSONIC_USERNAME = os.environ["SUBSONIC_USERNAME"]
SUBSONIC_PASSWORD = os.environ["SUBSONIC_PASSWORD"]
OUTPUT_LOCATION = os.environ.get("OUTPUT_LOCATION", "/music")
OUTPUT_COUNT = int(os.environ.get("OUTPUT_COUNT", "50"))
UID = os.environ.get("OUTPUT_UID", "1000")
GID = os.environ.get("OUTPUT_GID", "1000")
SUBSONIC_PLAYLIST = os.environ.get("SUBSONIC_PLAYLIST", "Radio")
DEEZER_USER_ID = os.environ.get("DEEZER_USER_ID", "")

DEEZER_FAVS_FOLDER = "Deezer_Favs"
DEEZER_FAVS_PLAYLIST = "Deezer Favs"

complained_on = {}
deezer_downloaded = set()


class SignalCatcher:
    interrupted = False

    def __init__(self):
        signal.signal(signal.SIGINT, self.exit_gracefully)
        signal.signal(signal.SIGTERM, self.exit_gracefully)

    def exit_gracefully(self, signum, frame):
        print("exiting..")
        self.interrupted = True


def get_valid_filename(name, spaces_to=None):
    s = str(name).strip()
    if spaces_to:
        s = s.replace(" ", spaces_to)

    s = re.sub(r"(?u)[^-\w. ]", "", s)
    return s


# Ensure the py-sonic library is installed.
try:
    from libsonic import Connection
except ImportError:
    print("The 'libsonic' library is not installed.")
    print("Please install it by running: pip install py-sonic")
    sys.exit(1)


def download_similar_songs(playlist_title, song: dict):
    count = 0

    folder_title = get_valid_filename(song["title"], spaces_to="_").lower()

    path = os.path.join(OUTPUT_LOCATION, folder_title)
    if os.path.exists(path):
        if path not in complained_on:
            print(
                f"Looks like folder named {folder_title} already exists in {OUTPUT_LOCATION}, skipping"
            )

        complained_on[path] = None
        return

    sp.run(f"mkdir -p {folder_title}", shell=True)
    sp.run(f"chmod a+rwx {folder_title}", shell=True)

    playlist_fn = f"{playlist_title}.m3u"
    sp.run(f"touch {folder_title}/'{playlist_fn}'", shell=True)

    print(f"Creating {playlist_fn}")

    downloaded = set()

    done = False
    fails_count = 0
    while not done:
        at_least_one = False
        songs = yt.get_similar_songs(song["id"])
        for similar in songs:
            if similar["id"] in downloaded:
                continue

            fn = f"{similar['author']} - {similar['title']}.opus"
            fn = get_valid_filename(fn)

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

            result_fn = m.group(1).replace("'", "")
            sp.check_output(f"chmod a+r '{result_fn}'", shell=True)
            sp.check_output(f"mv '{result_fn}' {folder_title}/'{fn}'", shell=True)
            result_fn = fn

            with open(f"{folder_title}/{playlist_fn}", "a") as f:
                f.write(result_fn)
                f.write("\n")

            print("*", result_fn)
            count += 1
            at_least_one = True
            downloaded.add(similar["id"])

            out = sp.check_output(
                f"rsync -av --owner --group --chown {UID}:{GID} {folder_title} {OUTPUT_LOCATION}/",
                shell=True,
            )
            print(out.decode("utf8"))

            if count > OUTPUT_COUNT:
                done = True
                break

        if not at_least_one:
            print("Youtube started to return same songs, exiting...")
            break


def get_deezer_favorites() -> list:
    url = f"https://api.deezer.com/user/{DEEZER_USER_ID}/tracks?limit=100"
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            data = json.loads(resp.read())
        return data.get("data", [])
    except Exception as e:
        print(f"Failed to fetch Deezer favorites: {e}")
        return []


def sync_deezer_favs():
    if not DEEZER_USER_ID:
        return

    tracks = get_deezer_favorites()
    if not tracks:
        return

    folder = os.path.join(OUTPUT_LOCATION, DEEZER_FAVS_FOLDER)
    playlist_fn = f"{DEEZER_FAVS_PLAYLIST}.m3u"
    sp.run(f"mkdir -p '{folder}'", shell=True)
    sp.run(f"chmod a+rwx '{folder}'", shell=True)
    sp.run(f"touch '{folder}/{playlist_fn}'", shell=True)

    for track in tracks:
        track_id = str(track["id"])
        if track_id in deezer_downloaded:
            continue

        artist = track.get("artist", {}).get("name", "")
        title = track.get("title", "")
        query = f"{artist} {title}"

        results = yt.search(query)
        if not results:
            print(f"[Deezer Favs] nothing found for: {query}")
            deezer_downloaded.add(track_id)
            continue

        song = results[0]
        fn = get_valid_filename(f"{song['author']} - {song['title']}.opus")
        dest_path = os.path.join(folder, fn)

        if os.path.exists(dest_path):
            deezer_downloaded.add(track_id)
            continue

        try:
            out = sp.check_output(
                f"yt-dlp -x --no-warnings --embed-metadata https://music.youtube.com/watch?v={song['id']}",
                shell=True,
            ).decode("utf8")
        except Exception as e:
            print(f"[Deezer Favs] yt-dlp failed: {e}")
            continue

        m = re.search(r'"(.*\.opus)"', out)
        if not m:
            print(f"[Deezer Favs] could not determine filename from: {out}")
            deezer_downloaded.add(track_id)
            continue

        result_fn = m.group(1).replace("'", "")
        sp.check_output(f"chmod a+r '{result_fn}'", shell=True)
        sp.check_output(f"mv '{result_fn}' '{dest_path}'", shell=True)

        with open(f"{folder}/{playlist_fn}", "a") as f:
            f.write(fn)
            f.write("\n")

        print(f"* [Deezer Favs] {fn}")
        deezer_downloaded.add(track_id)


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

    # Search for the playlist
    radio_playlist_id = None
    existing_playlists = set()

    for playlist in playlists.get("playlist", []):
        existing_playlists.add(playlist["name"])

        if playlist["name"] == SUBSONIC_PLAYLIST:
            radio_playlist_id = playlist.get("id")

    if radio_playlist_id:
        details = sub.getPlaylist(radio_playlist_id)["playlist"]
        songs = details.get("entry", [])

        if songs:
            for song in songs:
                playlist_title = get_valid_filename(song["title"])
                if playlist_title in existing_playlists:
                    continue

                query = f"{song.get('artist')} {song.get('title')}"
                results = yt.search(query)
                if len(results):
                    download_similar_songs(playlist_title, results[0])
                else:
                    print("...nothing found")

        else:
            print("The {SUBSONIC_PLAYLIST} playlist not found")
    else:
        print(f"The playlist named {SUBSONIC_PLAYLIST} was not found on your server.")


if __name__ == "__main__":
    catcher = SignalCatcher()
    print(f"Connecting to {SUBSONIC_SERVER_URL}")

    last_deezer_check = 0
    while not catcher.interrupted:
        get_radio_playlist(SUBSONIC_SERVER_URL, SUBSONIC_USERNAME, SUBSONIC_PASSWORD)

        if DEEZER_USER_ID and time.time() - last_deezer_check >= 60:
            sync_deezer_favs()
            last_deezer_check = time.time()

        time.sleep(30)
