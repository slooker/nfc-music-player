
# NFC tag UID → Navidrome album mapping
#
# Find album IDs in Navidrome:
#   1. Open https://music.slooker.us and browse to the album
#   2. The album ID appears in the URL (e.g. /album/abc123def456)
#   OR via Subsonic API:
#   curl "https://music.slooker.us/rest/getAlbumList.view?type=alphabeticalByName&u=<user>&p=<pass>&v=1.16.1&c=test&f=json"

playlists = {
    # Perfect Circle - Eat the Elephant
    "21761305": {
        "type": "album",
        "id": "REPLACE_WITH_NAVIDROME_ALBUM_ID",
        "shuffle": "false"
    },

    # Perfect Circle - Eat the Elephant
    "B94C0D05": {
        "type": "album",
        "id": "REPLACE_WITH_NAVIDROME_ALBUM_ID",
        "shuffle": "false"
    },


    ## TTRPG Music

    # Combat Music
    "B2AC41AE": {
        "type": "album",
        "id": "REPLACE_WITH_NAVIDROME_ALBUM_ID",
        "shuffle": "false"
    },

    # Marketplace Music
    "81E17905": {
        "type": "album",
        "id": "REPLACE_WITH_NAVIDROME_ALBUM_ID",
        "shuffle": "false"
    },

    # Harbor Music
    # "B94C0D05": {  # NOTE: duplicate key — same UID as "Perfect Circle" above; update one of these UIDs
    #     "type": "album",
    #     "id": "REPLACE_WITH_NAVIDROME_ALBUM_ID",
    #     "shuffle": "false",
    # },

    # Forest Music
    "43A2EB33": {
        "type": "album",
        "id": "REPLACE_WITH_NAVIDROME_ALBUM_ID",
        "shuffle": "false",
    }

}
