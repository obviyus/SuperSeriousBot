import requests


def reddit_parser(reddit_url: str) -> str:
    """Parse Reddit links for upvotes and comments"""
    text: str
    reddit_url = reddit_url[:-1] + ".json" if reddit_url[-1] == "/" else reddit_url

    r = requests.get(reddit_url, headers={'User-agent': 'SuperSeriousBot'}).json()
    if r[0]["kind"] != "Listing":
        return ""
    else:
        post_score = r[0]["data"]["children"][0]["data"]["score"]
        comments = r[0]["data"]["children"][0]["data"]["num_comments"]

    text = f"""`[ {post_score} upvotes | {comments} comments ]`"""

    return text
