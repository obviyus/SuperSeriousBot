import pafy


def youtube_parser(youtube_url: str) -> str:
    """Parse YouTube links for duration"""
    text: str

    video = pafy.new(youtube_url)
    duration = video.duration

    return f"`[ {duration} ]`"
