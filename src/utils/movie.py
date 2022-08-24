def get_fields(imdb_data):
    na_cover = (
        "https://i.imgur.com/A8SBkqe_d.jpg?max%20width=640&shape=thumb&fidelity=medium"
    )

    title_id = imdb_data.getID()

    fields = {
        "title": "N/A",
        "plot": "N/A",
        "end_year": None,
        "year": None,
        "genres": "N/A",
        "rating": "N/A",
        "kind": "N/A",
        "cast": "N/A",
        "long imdb title": "N/A",
        "cover url": na_cover,
        "full-size cover url": na_cover,
        "series title": "N/A",
        "season": "N/A",
        "episode": "N/A",
        "id": title_id,
        "directors": "N/A",
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
