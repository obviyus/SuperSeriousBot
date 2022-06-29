def scrub_dict(d: dict) -> dict:
    """
    Remove empty values from a dictionary.
    """
    if type(d) is dict:
        return dict(
            (k, scrub_dict(v))
            for k, v in d.items()
            if v and v != [""] and scrub_dict(v)
        )
    else:
        return d
