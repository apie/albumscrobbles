#!/usr/bin/env python3
from scrape import get_album_stats_inc_random, correct_album_stats, correct_overview_stats


def main(argv):
    if len(argv) < 2:
        raise Exception(
            'Give username as first argument. And optionally the range 7/30/90/180/365 as second argument. If you provide nothing, this implies an infinite range. If you provide "random", this implies a random period from your listening history. If you provide "overview", this implies an overview per year. Optional third argument is to drill down the overview. Optional fourth argument is to switch the overview drilldown to weekly.'
        )
    overview_per = None
    if len(argv) < 3:
        drange = None
    else:
        drange = argv[2]
        assert drange in ["random", "overview"] or int(drange) in (7, 30, 90, 180, 365)
        if drange == "overview" and len(argv) >= 4:
            overview_per = argv[3]
            assert len(overview_per) == 4, "Overview drilldown must be a year"
            if len(argv) == 5:
                overview_per += "week"
    username = argv[1]
    stats, blast_name, period = get_album_stats_inc_random(
        username, drange, overview_per
    )
    corrected = (
        correct_album_stats(stats)
        if drange != "overview"
        else correct_overview_stats(stats)
    )
    range_str = (
        "all time"
        if drange is None
        else f"the last {drange} days"
        if drange not in ["random", "overview"]
        else f"{blast_name} ({period}) (blast from the past)"
        if drange == "random"
        else "overview per year"
    )
    print(f"Album stats for {username} for {range_str}:")
    print()
    ARTIST_LEN = 30
    ALBUM_LEN = 40
    if drange == "overview":
        print(
            f"{overview_per[:4] if overview_per else 'Year':>4} {'Album':<{ALBUM_LEN}} {'Artist':<{ARTIST_LEN}}"
        )
        for per, corr in corrected.items():
            corr_list = list(corr)
            if not corr_list:
                print(f"{per:>4}")
            else:
                top_album = sorted(corr_list, key=lambda x: -x["album_scrobble_count"])[
                    0
                ]
                print(
                    f"{per:>4} {top_album['album_name']:<{ALBUM_LEN}} {top_album['artist_name']:<{ARTIST_LEN}}"
                )
    else:
        print(f"   {'Album':<{ALBUM_LEN}} {'Artist':<{ARTIST_LEN}}")
        for i, s in enumerate(
            sorted(list(corrected), key=lambda x: -x["album_scrobble_count"]), start=1
        ):
            print(
                f"{i:>2} {s['album_name']:<{ALBUM_LEN}} {s['artist_name']:<{ARTIST_LEN}}"
            )


if __name__ == "__main__":
    from sys import argv
    main(argv)
