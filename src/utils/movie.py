def get_fields(imdb_data):
    na_cover = (
        "https://i.imgur.com/A8SBkqe_d.jpg?max%20width=640&shape=thumb&fidelity=medium"
    )

    title_id = imdb_data.getID()

    fields = {
        "cast": "N/A",
        "cover url": na_cover,
        "directors": "N/A",
        "end_year": None,
        "episode": "N/A",
        "full-size cover url": na_cover,
        "genres": "N/A",
        "id": title_id,
        "kind": "N/A",
        "long imdb title": "N/A",
        "plot": "N/A",
        "rating": "N/A",
        "runtime": "N/A",
        "season": "N/A",
        "series title": "N/A",
        "title": "N/A",
        "year": None,
        "year": None,
    }

    for field in fields:
        value = imdb_data.get(field)
        if value:
            if isinstance(value, list):
                if field == "cast" or field == "directors":
                    value = ", ".join([n["name"] for n in value][0:4])
                else:
                    value = ", ".join(value).split("::")[0]

            fields[field] = value

    return fields
