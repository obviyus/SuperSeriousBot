from datetime import datetime
from typing import TYPE_CHECKING

import dateutil.relativedelta
import pytz
import requests
from dateutil.parser import parse

if TYPE_CHECKING:
    import telegram
    import telegram.ext

utc = pytz.UTC


def cases(update: 'telegram.Update', context: 'telegram.ext.CallbackContext') -> None:
    """Get COVID-19 India cases"""
    if update.message:
        message: 'telegram.Message' = update.message
    else:
        return

    CASES_ENDPOINT: str = "https://api.rootnet.in/covid19-in/stats/latest"
    r = requests.get(CASES_ENDPOINT).json()

    last_refreshed = parse(r["lastRefreshed"])
    text = f"""COVID-19 India Stats ({dateutil.relativedelta.relativedelta(datetime.now().replace(tzinfo=utc), last_refreshed.replace(tzinfo=utc)).hours} hours ago): """

    text += "\n\nTotal Cases: {:,}".format(r["data"]["summary"]["total"])
    text += "\nTotal Deaths: {:,}".format(r["data"]["summary"]["deaths"])

    TESTING_ENDPOINT: str = "https://api.rootnet.in/covid19-in/stats/testing/latest"
    text += "\nTotal Samples Tested: {:,}".format(requests.get(TESTING_ENDPOINT).json()["data"]["totalSamplesTested"])

    text += "\n\n**Regional Distribution:**"
    regional_cases = r["data"]["regional"]
    HISTORICAL_ENDPOINT: str = "https://api.rootnet.in/covid19-in/stats/history"
    regional_cases_prev = requests.get(HISTORICAL_ENDPOINT).json()["data"][-2]["regional"]
    present_vs_prev = []

    for i in range(len(regional_cases)):
        region_present = regional_cases[i]["totalConfirmed"]
        region_prev = regional_cases_prev[i]["totalConfirmed"]
        percent_change = (region_present / region_prev) * 100

        present_vs_prev.append((regional_cases[i]["loc"], region_present, percent_change))

    present_vs_prev = sorted(present_vs_prev, key=lambda x: x[1], reverse=True)
    for i in range(5):
        regional_cases = "{:,}".format(present_vs_prev[i][1])
        text += f"""\n{i + 1}. {present_vs_prev[i][0]} - {regional_cases}"""
        percent_change = present_vs_prev[i][2]
        if percent_change > 100:
            text += f" (↑{round(percent_change - 100, 2)}%)"
        elif percent_change < 100:
            text += f" (↓{round(100 - percent_change, 2)}%)"

    HOSPITALS_ENDPOINT: str = "https://api.rootnet.in/covid19-in/hospitals/beds"
    r = requests.get(HOSPITALS_ENDPOINT).json()
    text += "\n\nTotal Hospitals: {:,}".format(r["data"]["summary"]["totalHospitals"])
    text += "\nTotal Beds: {:,}".format(r["data"]["summary"]["totalBeds"])

    message.reply_text(text=text)
