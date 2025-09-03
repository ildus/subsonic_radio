import traceback
import ytmusicapi


def _connect() -> ytmusicapi.YTMusic | None:
    try:
        return ytmusicapi.YTMusic()
    except:
        print("Failed to connect to YTM:\033[0;33m")
        traceback.print_exc()
        print("\033[0m")

    return None


def _get_artist_names(artists: list) -> list:
    return [artist["name"] for artist in artists if artist["id"]]


def _get_artist_id(artists: list) -> str:
    a_id = ""
    for i in range(len(artists)):
        a_id = artists[i]["id"]
        if a_id:
            break

    return a_id


def _parse_single_result(yt: ytmusicapi.YTMusic, result: dict) -> dict | None:
    if result["resultType"] == "single":
        result["resultType"] = "album"

    item = {"type": result["resultType"], "top": False}
    if "category" in result:
        item["top"] = result["category"] == "Top result"
        if result["category"] in ["Profiles", "Episodes"]:
            return None

    if result["resultType"] == "artist":
        try:
            if result["category"] == "Top result":
                item["author"] = ", ".join(_get_artist_names(result["artists"]))
                item["id"] = _get_artist_id(result["artists"])
            else:
                item["author"] = result["artist"]
                item["id"] = result["browseId"]
        except:
            print("Failed to parse artist result:\033[0;33m")
            traceback.print_exc()
            print("\033[0m")
            return None
    elif result["resultType"] == "album":
        try:
            item["author"] = result["artists"][0]["name"]
            item["id"] = result["browseId"]
            item["title"] = result["title"]

            album = (
                yt.get_playlist(result["playlistId"])
                if result["playlistId"]
                else yt.get_album(result["browseId"])
            )
            item["contents"] = [
                {
                    "id": str(s["videoId"]),
                    "title": s["title"],
                    "type": "song",
                    "author": ", ".join(_get_artist_names(s["artists"])),
                    "author_id": _get_artist_id(s["artists"]),
                    "length": s["duration"],
                    "thumbnail": result["thumbnails"][0]["url"],
                }
                for s in album["tracks"]
                if s["videoId"]
            ]
        except:
            print("Failed to parse album result:\033[0;33m")
            traceback.print_exc()
            print("\033[0m")
            return None
    elif result["resultType"] == "playlist":
        try:
            album = yt.get_playlist(result["browseId"], limit=None)
            if "author" in result:
                item["author"] = result["author"]
            else:
                item["author"] = ", ".join(_get_artist_names(result["artists"]))
            item["id"] = result["browseId"]
            item["title"] = result["title"]
            item["contents"] = [
                {
                    "id": str(s["videoId"]),
                    "title": s["title"],
                    "type": "song",
                    "author": ", ".join(_get_artist_names(s["artists"])),
                    "author_id": _get_artist_id(s["artists"]),
                    "length": s["duration"],
                    "thumbnail": s["thumbnails"][0]["url"],
                }
                for s in album["tracks"]
                if s["videoId"]
            ]
        except:
            print("Failed to parse playlist result:\033[0;33m")
            traceback.print_exc()
            print("\033[0m")
            return None
    elif result["resultType"] in {"song", "video"}:
        try:
            if not result["videoId"]:
                return None
            item["id"] = str(result["videoId"])
            item["title"] = result["title"]
            item["author"] = ", ".join(_get_artist_names(result["artists"]))
            item["author_id"] = _get_artist_id(result["artists"])
            if "duration" in result:
                item["length"] = result["duration"]
            item["thumbnail"] = result["thumbnails"][0]["url"]

            # ytm sometimes returns videos as song results when filtered
            if "category" in result and result["category"] == "Songs":
                item["type"] = "song"
        except:
            print("Failed to parse song/video result:\033[0;33m")
            traceback.print_exc()
            print("\033[0m")
            return None

    return item


def _parse_results(data: list) -> list:
    yt = _connect()
    if yt is None:
        return []

    exp_types = {"album", "song", "video", "playlist", "artist", "single"}
    results = [
        _parse_single_result(yt, item)
        for item in data
        if item.get("resultType", "") in exp_types
    ]

    return [r for r in results if r]


def get_similar_songs(video_id: str, ignore: list | None = None) -> list:
    yt = _connect()
    if yt is None:
        return None

    ignore = ignore if ignore else []
    try:
        data = yt.get_watch_playlist(video_id, radio=True)["tracks"]
    except:
        return None

    acceptable_tracks = []
    for item in data:
        track = {
            "title": item["title"],
            "author": ", ".join(_get_artist_names(item["artists"])),
            "author_id": _get_artist_id(item["artists"]),
            "length": item["length"],
            "id": item["videoId"],
            "thumbnail": item["thumbnail"][0]["url"],
        }
        if not track["id"]:
            continue

        for id_ in ignore:
            if id_ == track["id"]:
                break
        else:  # nobreak
            acceptable_tracks.append(track)

    return acceptable_tracks


def get_song(id_: str) -> dict | None:
    yt = _connect()
    if yt is None:
        return None

    try:
        result = yt.get_song(id_)["videoDetails"]
    except:
        return None

    seconds = int(result["lengthSeconds"])
    minutes = seconds // 60
    seconds %= 60
    return {
        "top": True,
        "type": "video",
        "id": result["videoId"],
        "title": result["title"],
        "author": result["author"],
        "author_id": result["channelId"],
        "length": f"{minutes}:{seconds:02}",
        "thumbnail": result["thumbnail"]["thumbnails"][0],
    }


def get_artist(browse_id: str) -> list:
    yt = _connect()
    if yt is None:
        return []

    try:
        metadata = yt.get_artist(browse_id)
        artist = {"name": metadata["name"]}
        for group in ["albums", "singles"]:
            artist[group] = {}
            artist[group]["results"] = []
            if group not in metadata:
                continue

            if "params" in metadata[group]:
                artist[group]["results"] = yt.get_artist_albums(
                    metadata[group]["browseId"], metadata[group]["params"]
                )
            else:
                artist[group]["results"] = metadata[group]["results"]

        for group in ["songs", "videos", "playlists"]:
            if group in metadata:
                artist[group] = metadata[group]
            else:
                print("Artist has no", group)
    except:
        try:
            artist = yt.get_user(browse_id)
        except:
            print("Could not get artist:\033[0;31m")
            traceback.print_exc()
            print("\033[0m")
            return []

    data = []
    for group in ["songs", "albums", "singles", "videos", "playlists"]:
        content = []
        if group in artist:
            if group in {"songs", "videos"}:
                try:
                    yt.get_playlist(artist[group]["browseId"], limit=None)["tracks"]
                except:
                    content = artist[group].get("results", [])
            else:
                content = []
                for alb in artist[group]["results"]:
                    if not ("browseId" in alb or "playlistId" in alb):
                        print(f"Failed to get artist {group}:\033[0;33m")
                        print("browseId/playlistId missing")
                        print("\033[0m")
                        continue

                    content.append(
                        {
                            "title": alb["title"],
                            "browseId": (
                                alb["browseId" if "browseId" in alb else "playlistId"]
                            ),
                            "playlistId": alb.get(
                                "audioPlaylistId", alb.get("playlistId", None)
                            ),
                            "artists": [{"name": artist["name"], "id": browse_id}],
                            "thumbnails": alb["thumbnails"],
                        }
                    )

            for item in content:
                item["resultType"] = group[:-1]

            data.extend(content)

    return _parse_results(data)


def search(query: str, filter_: str = "") -> list:
    yt = _connect()
    if yt is None:
        return []

    try:
        if "?v=" in query and "/" in query:
            song = get_song(query.split("?v=")[-1].split("&")[0])
            return [song] if song else []
        if "youtu.be/" in query:
            song = get_song(query.split("youtu.be/")[-1].split("?")[0])
            return [song] if song else []

        data = (
            yt.search(query, filter=filter_, limit=100) if filter_ else yt.search(query)
        )
    except:
        return []

    return _parse_results(data)
